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

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Core.snapshot_pf_data import SnapshotData
import GridCal.Engine.Core.DataStructures as ds


class SnapshotOpfData(SnapshotData):

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nupfc, nhvdc, nload, ngen, nbatt, nshunt, nstagen, sbase):
        """

        :param nbus:
        :param nline:
        :param ndcline:
        :param ntr:
        :param nvsc:
        :param nhvdc:
        :param nload:
        :param ngen:
        :param nbatt:
        :param nshunt:
        :param nstagen:
        :param sbase:
        """
        SnapshotData.__init__(self, nbus=nbus, nline=nline,
                              ndcline=ndcline, ntr=ntr, nvsc=nvsc, nupfc=nupfc,
                              nhvdc=nhvdc, nload=nload, ngen=ngen,
                              nbatt=nbatt, nshunt=nshunt, nstagen=nstagen,
                              sbase=sbase, ntime=1)

        # overwrite with their opf version
        self.branch_data = ds.BranchOpfData(nbr=self.nbr, nbus=nbus, ntime=self.ntime)
        self.load_data = ds.LoadOpfData(nload=nload, nbus=nbus, ntime=self.ntime)
        self.battery_data = ds.BatteryOpfData(nbatt=nbatt, nbus=nbus, ntime=self.ntime)
        self.generator_data = ds.GeneratorOpfData(ngen=ngen, nbus=nbus, ntime=self.ntime)

    @property
    def battery_pmax(self):
        return self.battery_data.battery_pmax

    @property
    def battery_pmin(self):
        return self.battery_data.battery_pmin

    @property
    def battery_cost(self):
        return self.battery_data.battery_cost[:, 0]

    @property
    def generator_pmax(self):
        return self.generator_data.generator_pmax

    @property
    def generator_pmin(self):
        return self.generator_data.generator_pmin

    @property
    def generator_dispatchable(self):
        return self.generator_data.generator_dispatchable

    @property
    def generator_cost(self):
        return self.generator_data.generator_cost[:, 0]

    @property
    def generator_p(self):
        return self.generator_data.generator_p[:, 0]

    @property
    def generator_active(self):
        return self.generator_data.generator_active[:, 0]

    @property
    def load_active(self):
        return self.load_data.load_active[:, 0]

    @property
    def load_s(self):
        return self.load_data.load_s[:, 0]

    @property
    def load_cost(self):
        return self.load_data.load_cost[:, 0]

    @property
    def branch_R(self):
        return self.branch_data.R

    @property
    def branch_X(self):
        return self.branch_data.X

    @property
    def branch_active(self):
        return self.branch_data.branch_active[:, 0]

    @property
    def branch_cost(self):
        return self.branch_data.branch_cost[:, 0]

    def get_island(self, bus_idx, time_idx=None) -> "SnapshotData":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param time_idx: array of time indices (or None for all time indices)
        :return: SnapshotData
        """

        # find the indices of the devices of the island
        line_idx = self.line_data.get_island(bus_idx)
        dc_line_idx = self.dc_line_data.get_island(bus_idx)
        tr_idx = self.transformer_data.get_island(bus_idx)
        vsc_idx = self.vsc_data.get_island(bus_idx)
        hvdc_idx = self.hvdc_data.get_island(bus_idx)
        br_idx = self.branch_data.get_island(bus_idx)
        upfc_idx = self.upfc_data.get_island(bus_idx)

        load_idx = self.load_data.get_island(bus_idx)
        stagen_idx = self.static_generator_data.get_island(bus_idx)
        gen_idx = self.generator_data.get_island(bus_idx)
        batt_idx = self.battery_data.get_island(bus_idx)
        shunt_idx = self.shunt_data.get_island(bus_idx)

        nc = SnapshotOpfData(nbus=len(bus_idx),
                             nline=len(line_idx),
                             ndcline=len(dc_line_idx),
                             ntr=len(tr_idx),
                             nvsc=len(vsc_idx),
                             nhvdc=len(hvdc_idx),
                             nload=len(load_idx),
                             ngen=len(gen_idx),
                             nbatt=len(batt_idx),
                             nshunt=len(shunt_idx),
                             nstagen=len(stagen_idx),
                             nupfc=len(upfc_idx),
                             sbase=self.Sbase)

        # set the original indices
        nc.original_bus_idx = bus_idx
        nc.original_branch_idx = br_idx
        nc.original_line_idx = line_idx
        nc.original_tr_idx = tr_idx
        nc.original_dc_line_idx = dc_line_idx
        nc.original_vsc_idx = vsc_idx
        nc.original_hvdc_idx = hvdc_idx
        nc.original_gen_idx = gen_idx
        nc.original_bat_idx = batt_idx
        nc.original_load_idx = load_idx
        nc.original_stagen_idx = stagen_idx
        nc.original_shunt_idx = shunt_idx

        # slice data
        nc.bus_data = self.bus_data.slice(bus_idx, time_idx)
        nc.branch_data = self.branch_data.slice(br_idx, bus_idx, time_idx)
        nc.line_data = self.line_data.slice(line_idx, bus_idx, time_idx)
        nc.transformer_data = self.transformer_data.slice(tr_idx, bus_idx, time_idx)
        nc.hvdc_data = self.hvdc_data.slice(hvdc_idx, bus_idx, time_idx)
        nc.vsc_data = self.vsc_data.slice(vsc_idx, bus_idx, time_idx)
        nc.dc_line_data = self.dc_line_data.slice(dc_line_idx, bus_idx, time_idx)
        nc.load_data = self.load_data.slice(load_idx, bus_idx, time_idx)
        nc.static_generator_data = self.static_generator_data.slice(stagen_idx, bus_idx, time_idx)
        nc.battery_data = self.battery_data.slice(batt_idx, bus_idx, time_idx)
        nc.generator_data = self.generator_data.slice(gen_idx, bus_idx, time_idx)
        nc.shunt_data = self.shunt_data.slice(shunt_idx, bus_idx, time_idx)

        return nc


def compile_snapshot_opf_circuit(circuit: MultiCircuit, apply_temperature=False,
                                 branch_tolerance_mode=BranchImpedanceMode.Specified) -> SnapshotOpfData:
    """
    Compile the information of a circuit and generate the pertinent power flow islands
    :param circuit: Circuit instance
    :param apply_temperature:
    :param branch_tolerance_mode:
    :return: list of NumericIslands
    """

    logger = Logger()
    opf_results = None

    # declare the numerical circuit
    nc = SnapshotOpfData(nbus=0,
                         nline=0,
                         ndcline=0,
                         ntr=0,
                         nvsc=0,
                         nupfc=0,
                         nhvdc=0,
                         nload=0,
                         ngen=0,
                         nbatt=0,
                         nshunt=0,
                         nstagen=0,
                         sbase=circuit.Sbase)

    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    nc.bus_data = ds.circuit_to_data.get_bus_data(circuit)
    nc.load_data = ds.circuit_to_data.get_load_data(circuit, bus_dict, opf_results, opf=True)
    nc.static_generator_data = ds.circuit_to_data.get_static_generator_data(circuit, bus_dict)
    nc.generator_data = ds.circuit_to_data.get_generator_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results, opf=True)
    nc.battery_data = ds.circuit_to_data.get_battery_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results, opf=True)
    nc.shunt_data = ds.circuit_to_data.get_shunt_data(circuit, bus_dict, nc.bus_data.Vbus, logger)
    nc.line_data = ds.circuit_to_data.get_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.transformer_data = ds.circuit_to_data.get_transformer_data(circuit, bus_dict)
    nc.vsc_data = ds.circuit_to_data.get_vsc_data(circuit, bus_dict)
    nc.upfc_data = ds.circuit_to_data.get_upfc_data(circuit, bus_dict)

    nc.dc_line_data = ds.circuit_to_data.get_dc_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.branch_data = ds.circuit_to_data.get_branch_data(circuit, bus_dict, nc.bus_data.Vbus,
                                                        apply_temperature, branch_tolerance_mode, opf=True)
    nc.hvdc_data = ds.circuit_to_data.get_hvdc_data(circuit, bus_dict, nc.bus_data.bus_types)

    nc.consolidate_information()

    return nc

