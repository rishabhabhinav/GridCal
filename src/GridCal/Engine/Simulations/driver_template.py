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
from typing import List

import numpy as np
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class DummySignal:

    def __init__(self, tpe=str):
        self.tpe = tpe

    def emit(self, val=''):
        pass


class DriverTemplate:

    tpe = SimulationTypes.TemplateDriver
    name = 'Template'

    def __init__(self, grid: MultiCircuit):
        self.progress_signal = DummySignal()
        self.progress_text = DummySignal(str)
        self.done_signal = DummySignal()

        self.grid = grid

        self.results = None

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        return list()

    def run(self):
        pass

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


class TimeSeriesDriverTemplate(DriverTemplate):

    def __init__(self, grid: MultiCircuit, start_=0, end_=None):

        DriverTemplate.__init__(self, grid=grid)

        self.start_ = start_

        self.indices = self.grid.time_profile

        if end_ is not None:
            self.end_ = end_
        else:
            self.end_ = len(self.grid.time_profile)

    def get_time_indices(self):
        """
        Get an array of indices of the time steps selected within the start-end interval
        :return: np.array[int]
        """
        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        return np.arange(self.start_, self.end_ + 1)
