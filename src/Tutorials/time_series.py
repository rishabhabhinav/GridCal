import numpy as np
import pandas as pd
import datetime as dt
from GridCal.Engine import *

####################################################################################################################
# Define the circuit
#
# A circuit contains all the grid information regardless of the islands formed or the amount of devices
####################################################################################################################

# create a circuit

grid = MultiCircuit(name='lynn 5 bus')

# let's create a master profile
date0 = dt.datetime(2021, 1, 1)
time_array = pd.DatetimeIndex([date0 + dt.timedelta(hours=i) for i in range(26)])
x = np.linspace(-np.pi, np.pi, len(time_array))
y = np.abs(np.sin(x))
df_0 = pd.DataFrame(data=y, index=time_array)  # complex values

# set the grid master time profile
grid.time_profile = df_0.index

####################################################################################################################
# Define the buses
####################################################################################################################
# I will define this bus with all the properties so you see
bus1 = Bus(name='Bus1',
           vnom=10,   # Nominal voltage in kV
           vmin=0.9,  # Bus minimum voltage in per unit
           vmax=1.1,  # Bus maximum voltage in per unit
           xpos=0,    # Bus x position in pixels
           ypos=0,    # Bus y position in pixels
           height=0,  # Bus height in pixels
           width=0,   # Bus width in pixels
           active=True,   # Is the bus active?
           is_slack=False,  # Is this bus a slack bus?
           area='Defualt',  # Area (for grouping purposes only)
           zone='Default',  # Zone (for grouping purposes only)
           substation='Default'  # Substation (for grouping purposes only)
           )

# the rest of the buses are defined with the default parameters
bus2 = Bus(name='Bus2')
bus3 = Bus(name='Bus3')
bus4 = Bus(name='Bus4')
bus5 = Bus(name='Bus5')

# add the bus objects to the circuit
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5)

####################################################################################################################
# Add the loads
####################################################################################################################

# In GridCal, the loads, generators ect are stored within each bus object:

# we'll define the first load completely
l2 = Load(name='Load',
          G=0, B=0,  # admittance of the ZIP model in MVA at the nominal voltage
          Ir=0, Ii=0,  # Current of the ZIP model in MVA at the nominal voltage
          P=40, Q=20,  # Power of the ZIP model in MVA
          active=True,  # Is active?
          mttf=0.0,  # Mean time to failure
          mttr=0.0  # Mean time to recovery
          )
grid.add_load(bus2, l2)

# Define the others with the default parameters
grid.add_load(bus3, Load(P=25, Q=15))
grid.add_load(bus4, Load(P=40, Q=20))
grid.add_load(bus5, Load(P=50, Q=20))

####################################################################################################################
# Add the generators
####################################################################################################################

g1 = Generator(name='gen',
               active_power=0.0,  # Active power in MW, since this generator is used to set the slack , is 0
               voltage_module=1.0,  # Voltage set point to control
               Qmin=-9999,  # minimum reactive power in MVAr
               Qmax=9999,  # Maximum reactive power in MVAr
               Snom=9999,  # Nominal power in MVA
               power_prof=None,  # power profile
               vset_prof=None,  # voltage set point profile
               active=True  # Is active?
               )
grid.add_generator(bus1, g1)

####################################################################################################################
# Add the lines
####################################################################################################################

br1 = Branch(bus_from=bus1,
             bus_to=bus2,
             name='Line 1-2',
             r=0.05,  # resistance of the pi model in per unit
             x=0.11,  # reactance of the pi model in per unit
             g=1e-20,  # conductance of the pi model in per unit
             b=0.02,  # susceptance of the pi model in per unit
             rate=50,  # Rate in MVA
             tap=1.0,  # Tap value (value close to 1)
             shift_angle=0,  # Tap angle in radians
             active=True,  # is the branch active?
             mttf=0,  # Mean time to failure
             mttr=0,  # Mean time to recovery
             branch_type=BranchType.Line,  # Branch type tag
             length=1,  # Length in km (to be used with templates)
             template=BranchTemplate()  # Branch template (The default one is void)
             )
grid.add_branch(br1)

grid.add_branch(Branch(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
grid.add_branch(Branch(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=80))
grid.add_branch(Branch(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=3))
grid.add_branch(Branch(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
grid.add_branch(Branch(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
grid.add_branch(Branch(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

####################################################################################################################
# Overwrite the default profiles with the custom ones
####################################################################################################################

for load in grid.get_loads():
    load.P_prof = load.P * df_0.values[:, 0]
    load.Q_prof = load.Q * df_0.values[:, 0]

for gen in grid.get_static_generators():
    gen.P_prof = gen.Q * df_0.values[:, 0]
    gen.Q_prof = gen.Q * df_0.values[:, 0]

for gen in grid.get_generators():
    gen.P_prof = gen.P * df_0.values[:, 0]

####################################################################################################################
# Run a power flow simulation
####################################################################################################################

# We need to specify power flow options
pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                              verbose=False,  # Verbose option where available
                              tolerance=1e-6,  # power error in p.u.
                              max_iter=25,  # maximum iteration number
                              control_q=True  # if to control the reactive power
                              )

# Declare and execute the power flow simulation
pf = PowerFlowDriver(grid, pf_options)
pf.run()

writer = pd.ExcelWriter('Results.xlsx')
# now, let's compose a nice DataFrame with the voltage results
headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
Vm = np.abs(pf.results.voltage)
Va = np.angle(pf.results.voltage, deg=True)
Vre = pf.results.voltage.real
Vim = pf.results.voltage.imag
data = np.c_[Vm, Va, Vre, Vim]
v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
# print('\n', v_df)
v_df.to_excel(writer, sheet_name='V')

# Let's do the same for the branch results
headers = ['Loading (%)', 'Power from (MVA)']
loading = np.abs(pf.results.loading) * 100
power = np.abs(pf.results.Sf)
data = np.c_[loading, power]
br_df = pd.DataFrame(data=data, columns=headers, index=grid.branch_names)
br_df.to_excel(writer, sheet_name='Br')

# Finally the execution metrics
print('\nError:', pf.results.error)
print('Elapsed time (s):', pf.results.elapsed, '\n')

####################################################################################################################
# Run a time series power flow simulation
####################################################################################################################

ts = TimeSeries(grid=grid,
                options=pf_options,
                opf_time_series_results=None,
                start_=0,
                end_=None)

ts.run()

print()
print('-' * 200)
print('Time series')
print('-' * 200)
print('Voltage time series')
df_voltage = pd.DataFrame(data=np.abs(ts.results.voltage), columns=grid.bus_names, index=grid.time_profile)
df_voltage.to_excel(writer, sheet_name='Vts')
print(df_voltage)

writer.close()
