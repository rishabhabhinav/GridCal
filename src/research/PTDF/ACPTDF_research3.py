# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
import pandas as pd
import numba as nb
import time
from warnings import warn
import scipy.sparse as sp
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve, inv
from matplotlib import pyplot as plt
from GridCal.Engine import *


def SysMat(Y, Ys, pq, pvpq):
    """
    Computes the system Jacobian matrix in polar coordinates
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    A11 = -Ys.imag[np.ix_(pvpq, pvpq)]
    A12 = Y.real[np.ix_(pvpq, pq)]
    A21 = -Ys.real[np.ix_(pq, pvpq)]
    A22 = -Y.imag[np.ix_(pq, pq)]

    Asys = sp.vstack([sp.hstack([A11, A12]),
                      sp.hstack([A21, A22])], format="csc")

    return Asys


def compute_acptdf(Ybus, Yseries, Yf, Yt, Cf, V, pq, pv, distribute_slack):
    """
    Compute the AC-PTDF
    :param Ybus: admittance matrix
    :param Yf: Admittance matrix of the buses "from"
    :param Yt: Admittance matrix of the buses "to"
    :param Cf: Connectivity branch - bus "from"
    :param V: voltages array
    :param Ibus: array of currents
    :param pq: array of pq node indices
    :param pv: array of pv node indices
    :return: AC-PTDF matrix (branches, buses)
    """
    n = len(V)
    pvpq = np.r_[pv, pq]
    npq = len(pq)

    # compute the Jacobian
    J = SysMat(Ybus, Yseries, pq, pvpq)

    if distribute_slack:
        dP = np.ones((n, n)) * (-1 / (n - 1))
        for i in range(n):
            dP[i, i] = 1.0
    else:
        dP = np.eye(n, n)

    # compose the compatible array (the Q increments are considered zero
    dQ = np.zeros((npq, n))
    # dQ = np.eye(n, n)[pq, :]
    dS = np.r_[dP[pvpq, :], dQ]

    # solve the voltage increments
    dx = spsolve(J, dS)

    # compute branch derivatives
    If = Yf * V
    E = V / np.abs(V)
    Vdiag = sp.diags(V)
    Vdiag_conj = sp.diags(np.conj(V))
    Ediag = sp.diags(E)
    Ediag_conj = sp.diags(np.conj(E))
    If_diag_conj = sp.diags(np.conj(If))

    Yf_conj = Yf.copy()
    Yf_conj.data = np.conj(Yf_conj.data)
    Yt_conj = Yt.copy()
    Yt_conj.data = np.conj(Yt_conj.data)

    dSf_dVa = 1j * (If_diag_conj * Cf * Vdiag - sp.diags(Cf * V) * Yf_conj * Vdiag_conj)
    dSf_dVm = If_diag_conj * Cf * Ediag - sp.diags(Cf * V) * Yf_conj * Ediag_conj

    # compose the final AC-PTDF
    dPf_dVa = dSf_dVa.real[:, pvpq]
    dPf_dVm = dSf_dVm.real[:, pq]
    PTDF = sp.hstack((dPf_dVa, dPf_dVm)) * dx

    return PTDF


def make_lodf(circuit: SnapshotCircuit, PTDF, correct_values=True):
    """

    :param circuit:
    :param PTDF: PTDF matrix in numpy array form
    :return:
    """
    nl = circuit.nbr

    # compute the connectivity matrix
    Cft = circuit.C_branch_bus_f - circuit.C_branch_bus_t

    H = PTDF * Cft.T

    # old code
    # h = sp.diags(H.diagonal())
    # LODF = H / (np.ones((nl, nl)) - h * np.ones(nl))

    # divide each row of H by the vector 1 - H.diagonal
    # LODF = H / (1 - H.diagonal())
    # replace possible nan and inf
    # LODF[LODF == -np.inf] = 0
    # LODF[LODF == np.inf] = 0
    # LODF = np.nan_to_num(LODF)

    # this loop avoids the divisions by zero
    # in those cases the LODF column should be zero
    LODF = np.zeros((nl, nl))
    div = 1 - H.diagonal()
    for j in range(H.shape[1]):
        if div[j] != 0:
            LODF[:, j] = H[:, j] / div[j]

    # replace the diagonal elements by -1
    # old code
    # LODF = LODF - sp.diags(LODF.diagonal()) - sp.eye(nl, nl), replaced by:
    for i in range(nl):
        LODF[i, i] = - 1.0

    if correct_values:
        i1, j1 = np.where(LODF > 1)
        for i, j in zip(i1, j1):
            LODF[i, j] = 1

        i2, j2 = np.where(LODF < -1)
        for i, j in zip(i2, j2):
            LODF[i, j] = -1

    return LODF


def get_branch_time_series(circuit: TimeCircuit, PTDF):
    """

    :param grid:
    :return:
    """

    # option 2: call the power directly
    P = circuit.Sbus.real
    Pbr = np.dot(PTDF, P).T * circuit.Sbase

    return Pbr


def multiple_failure_old(flows, LODF, beta, delta, alpha):
    """

    :param flows: array of all the pre-contingency flows
    :param LODF: Line Outage Distribution Factors Matrix
    :param beta: index of the first failed line
    :param delta: index of the second failed line
    :param alpha: index of the line where you want to see the effects
    :return: post contingency flow in the line alpha
    """
    # multiple contingency matrix
    M = np.ones((2, 2))
    M[0, 1] = -LODF[beta, delta]
    M[1, 0] = -LODF[delta, beta]

    # normal flows of the lines beta and delta
    F = flows[[beta, delta]]

    # contingency flows after failing the ines beta and delta
    Ff = np.linalg.solve(M, F)

    # flow delta in the line alpha after the multiple contingency of the lines beta and delta
    L = LODF[alpha, :][[beta, delta]]
    dFf_alpha = np.dot(L, Ff)

    return F[alpha] + dFf_alpha


def multiple_failure(flows, LODF, failed_idx):
    """
    From the paper:
    Multiple Element Contingency Screening
        IEEE TRANSACTIONS ON POWER SYSTEMS, VOL. 26, NO. 3, AUGUST 2011
        C. Matthew Davis and Thomas J. Overbye
    :param flows: array of all the pre-contingency flows (the base flows)
    :param LODF: Line Outage Distribution Factors Matrix
    :param failed_idx: indices of the failed lines
    :return: all post contingency flows
    """
    # multiple contingency matrix
    M = -LODF[np.ix_(failed_idx, failed_idx)]
    for i in range(len(failed_idx)):
        M[i, i] = 1.0

    # normal flows of the failed lines indicated by failed_idx
    F = flows[failed_idx]

    # Affected flows after failing the lines indicated by failed_idx
    Ff = np.linalg.solve(M, F)

    # flow delta in the line alpha after the multiple contingency of the lines indicated by failed_idx
    L = LODF[:, failed_idx]
    dFf_alpha = np.dot(L, Ff)

    # return the final contingency flow as the base flow plus the contingency flow delta
    return flows + dFf_alpha


def get_n_minus_1_flows(circuit: MultiCircuit):

    opt = PowerFlowOptions()
    branches = circuit.get_branches()
    m = circuit.get_branch_number()
    Pmat = np.zeros((m, m))  # monitored, contingency

    for c, branch in enumerate(branches):

        if branch.active:
            branch.active = False

            pf = PowerFlowDriver(circuit, opt)
            pf.run()
            Pmat[:, c] = pf.results.Sbranch.real

            branch.active = True

    return Pmat


def check_lodf(grid: MultiCircuit):

    flows_n1_nr = get_n_minus_1_flows(grid)

    # assume 1 island
    nc = compile_snapshot_circuit(grid)
    islands = split_into_islands(nc)
    circuit = islands[0]

    PTDF = compute_acptdf(Ybus=circuit.Ybus,
                          Yseries=circuit.Yseries,
                          Yf=circuit.Yf,
                          Yt=circuit.Yt,
                          Cf=circuit.C_branch_bus_f,
                          V=circuit.Vbus,
                          pq=circuit.pq,
                          pv=circuit.pv,
                          distribute_slack=True)
    LODF = make_lodf(circuit, PTDF)

    Pbus = circuit.get_injections(False).real
    flows_n = np.dot(PTDF, Pbus)

    nl = circuit.nbr
    flows_n1 = np.zeros((nl, nl))
    for c in range(nl):  # branch that fails (contingency)
        # for m in range(nl):  # branch to monitor
        #     flows_n1[m, c] = flows_n[m] + LODF[m, c] * flows_n[c]
        flows_n1[:, c] = flows_n[:] + LODF[:, c] * flows_n[c]

    return flows_n, flows_n1_nr, flows_n1


def test_ptdf(grid):
    """
    Sigma-distances test
    :param grid:
    :return:
    """
    nc = compile_snapshot_circuit(grid)
    islands = split_into_islands(nc)
    circuit = islands[0]  # pick the first island

    pf_driver = PowerFlowDriver(grid, PowerFlowOptions())
    pf_driver.run()

    PTDF = compute_acptdf(Ybus=circuit.Ybus,
                          Yseries=circuit.Yseries,
                          Yf=circuit.Yf,
                          Yt=circuit.Yt,
                          Cf=circuit.C_branch_bus_f,
                          V=circuit.Vbus,
                          pq=circuit.pq,
                          pv=circuit.pv,
                          distribute_slack=False)

    print('PTDF:')
    print(PTDF)


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(threshold=sys.maxsize, linewidth=200000000)
    # np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case5.m'
    # fname = '/home/santi/Descargas/matpower-fubm-master/data/case30.m'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/PGOC_6bus.gridcal'
    grid_ = FileOpen(fname).open()

    test_ptdf(grid_)
    name = os.path.splitext(fname.split(os.sep)[-1])[0]
    method = 'ACPTDF (No Jacobian, V=1)'
    nc_ = compile_snapshot_circuit(grid_)
    islands_ = split_into_islands(nc_)
    circuit_ = islands_[0]

    H_ = compute_acptdf(Ybus=circuit_.Ybus,
                        Yseries=circuit_.Yseries,
                        Yf=circuit_.Yf,
                        Yt=circuit_.Yt,
                        Cf=circuit_.C_branch_bus_f,
                        V=circuit_.Vbus,
                        pq=circuit_.pq,
                        pv=circuit_.pv,
                        distribute_slack=False)

    LODF_ = make_lodf(circuit_, H_)

    if H_.shape[0] < 50:
        print('PTDF:\n', H_)
        print('LODF:\n', LODF_)

    flows_n_, flows_n1_nr_, flows_n1_ = check_lodf(grid_)

    # in the case of the grid PGOC_6bus
    flows_multiple = multiple_failure(flows=flows_n_,
                                      LODF=LODF_,
                                      failed_idx=[1, 5])  # failed lines 2 and 6

    Pn1_nr_df = pd.DataFrame(data=flows_n1_nr_, index=nc_.branch_names, columns=nc_.branch_names)
    flows_n1_df = pd.DataFrame(data=flows_n1_, index=nc_.branch_names, columns=nc_.branch_names)

    # plot N-1
    fig = plt.figure(figsize=(12, 8))
    title = 'N-1 with ' + method + ' (' + name + ')'
    fig.suptitle(title)
    ax1 = fig.add_subplot(221)
    ax2 = fig.add_subplot(222)
    ax3 = fig.add_subplot(223)

    Pn1_nr_df.plot(ax=ax1, legend=False)
    flows_n1_df.plot(ax=ax2, legend=False)
    diff = Pn1_nr_df - flows_n1_df
    diff.plot(ax=ax3, legend=False)

    ax1.set_title('Newton-Raphson N-1 flows')
    ax2.set_title('PTDF N-1 flows')
    ax3.set_title('Difference')
    fig.savefig(title + '.png')

    # ------------------------------------------------------------------------------------------------------------------
    # Perform real time series
    # ------------------------------------------------------------------------------------------------------------------
    if grid_.time_profile is not None:
        grid_.ensure_profiles_exist()
        nc_ts = compile_time_circuit(grid_)
        islands_ts = split_time_circuit_into_islands(nc_ts)
        circuit_ts = islands_ts[0]

        pf_options = PowerFlowOptions()
        ts_driver = TimeSeries(grid=grid_, options=pf_options)
        ts_driver.run()
        Pbr_nr = ts_driver.results.Sbranch.real
        df_Pbr_nr = pd.DataFrame(data=Pbr_nr, columns=circuit_ts.branch_names, index=circuit_ts.time_array)

        # Compute the PTDF based flows
        Pbr_ptdf = get_branch_time_series(circuit=circuit_ts, PTDF=H_)
        df_Pbr_ptdf = pd.DataFrame(data=Pbr_ptdf, columns=circuit_ts.branch_names, index=circuit_ts.time_array)

        # plot
        fig = plt.figure(figsize=(12, 8))
        title = 'Flows with ' + method + ' (' + name + ')'
        fig.suptitle(title)

        ax1 = fig.add_subplot(221)
        ax2 = fig.add_subplot(222)
        ax3 = fig.add_subplot(223)

        df_Pbr_nr.plot(ax=ax1, legend=False)
        df_Pbr_ptdf.plot(ax=ax2, legend=False)
        diff = df_Pbr_nr - df_Pbr_ptdf
        diff.plot(ax=ax3, legend=False)

        ax1.set_title('Newton-Raphson flows')
        ax2.set_title('PTDF flows')
        ax3.set_title('Difference')
        fig.savefig(title + '.png')

    plt.show()

