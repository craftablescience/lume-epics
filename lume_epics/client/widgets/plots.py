"""
The plots module contains bokeh figure based widgets. These widgets are initialized with
variables and a lume_epics.client.controller.Controller for interfacing with the EPICS
process variables.
"""

from typing import List
import logging
import numpy as np

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, ColorMapper, Button
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.models.widgets import Select

from lume_model.variables import Variable, ImageVariable, ScalarVariable
from lume_epics.client.controller import (
    Controller,
    DEFAULT_IMAGE_DATA,
    DEFAULT_SCALAR_VALUE,
)
from lume_epics.client.monitors import PVImage, PVTimeSeries

logger = logging.getLogger(__name__)


class ImagePlot:
    """
    Object for viewing and updating an image plot.

    Attributes:
        live_variable (str): Current variable to be displayed

        source (ColumnDataSource): Data source for the viewer.

        pv_monitors (PVImage): Monitors for the process variables.

        plot (Figure): Bokeh figure object for rendering.

        img_obj (GlyphRenderer): Bokeh glyph renderer for displaying image.

    Example:

        ```

        # controller initialized to use Channel Access
        controller = Controller("ca")

        value_table = ImagePlot(
                [output_variables["image_variable"]],
                controller,
            )

        ```
    """

    def __init__(
        self,
        variables: List[ImageVariable],
        controller: Controller,
        x_range: List[float] = None,
        y_range: List[float] = None,
    ) -> None:
        """
        Initialize monitors, current process variable, and data source.

        Args:
            variables (List[ImageVariable]): List of image variables to include in plot

            controller (Controller): Controller object for getting pv values

        """
        self.pv_monitors = {}
        self._x_range = x_range
        self._y_range = y_range

        for variable in variables:
            self.pv_monitors[variable.name] = PVImage(variable, controller)

        self.live_variable = list(self.pv_monitors.keys())[0]

        image_data = DEFAULT_IMAGE_DATA

        image_data["image"][0] = np.flipud(image_data["image"][0].T)

        self.source = ColumnDataSource(image_data)

    def build_plot(
        self, palette: tuple = None, color_mapper: ColorMapper = None
    ) -> None:
        """
        Creates the plot object.

        Args:
            palette (Optional[tuple]): Bokeh color palette to use for plot.

            color_mapper (Optional[ColorMapper]): Bokeh color mapper for rendering
                plot.

        """
        # create plot
        self.plot = figure(
            tooltips=[("x", "$x"), ("y", "$y"), ("value", "@image")],
            sizing_mode="scale_both",
            x_range=self._x_range,
            y_range=self._y_range,
        )
        self.plot.x_range.range_padding = self.plot.y_range.range_padding = 0

        if color_mapper:
            self.plot.image(
                name="image_plot",
                image="image",
                x="x",
                y="y",
                dw="dw",
                dh="dh",
                source=self.source,
                color_mapper=color_mapper,
            )

        elif palette:
            self.plot.image(
                name="image_plot",
                image="image",
                x="x",
                y="y",
                dw="dw",
                dh="dh",
                source=self.source,
                palette=palette,
            )

        else:
            raise Exception(
                "Must provide palette or color mapper during ImagePlot construction."
            )

        axis_labels = self.pv_monitors[self.live_variable].axis_labels
        axis_units = self.pv_monitors[self.live_variable].axis_units

        x_axis_label = axis_labels[0]
        y_axis_label = axis_labels[1]

        if axis_units:
            x_axis_label += " (" + axis_units[0] + ")"
            y_axis_label += " (" + axis_units[1] + ")"

        self.plot.xaxis.axis_label = x_axis_label
        self.plot.yaxis.axis_label = y_axis_label

    def update(self, live_variable: str = None) -> None:
        """
        Callback which updates the plot to reflect updated process variable values or
        new process variable.

        Args:
            live_variable (str): Variable to display
        """
        # update internal pv trackinng
        if live_variable:
            self.live_variable = live_variable

        # update axis and labels
        axis_labels = self.pv_monitors[self.live_variable].axis_labels
        axis_units = self.pv_monitors[self.live_variable].axis_units

        x_axis_label = axis_labels[0]
        y_axis_label = axis_labels[1]

        if axis_units:
            x_axis_label += " (" + axis_units[0] + ")"
            y_axis_label += " (" + axis_units[1] + ")"

        self.plot.xaxis.axis_label = x_axis_label
        self.plot.yaxis.axis_label = y_axis_label

        # get image data
        image_data = self.pv_monitors[self.live_variable].poll()
        image_data["image"][0] = np.flipud(image_data["image"][0].T)

        self.source.data.update(image_data)


class Striptool:
    """
    View for striptool display.

    Attributes:

        live_variable (str): Variable to be displayed.

        source (ColumnDataSource): Data source for the striptool view.

        pv_monitors (PVScalarMonitor): Monitors for the tracked process variables.

        plot (Figure): Bokeh figure object.

    """

    def __init__(
        self,
        variables: List[ScalarVariable],
        controller: Controller,
        limit: int = None,
        aspect_ratio: float = 1.05,
    ) -> None:
        """
        Set up monitors, current process variable, and data source.

        Args:
            variables (List[ScalarVariable]): List of variables to display with striptool

            controller (Controller): Controller object for getting process variable values

            limit (int): Maximimum steps for striptool to render

            aspect_ratio (float): Ratio of width to height

        """
        self.pv_monitors = {}

        for variable in variables:
            self.pv_monitors[variable.name] = PVTimeSeries(variable, controller)

        self.live_variable = list(self.pv_monitors.keys())[0]

        ts = []
        ys = []
        self.source = ColumnDataSource(dict(x=ts, y=ys))
        self.reset_button = Button(label="Reset")
        self.reset_button.on_click(self._reset_values)
        self._aspect_ratio = aspect_ratio
        self._limit = limit
        self.selection = Select(
            title="Variable to plot:",
            value=self.live_variable,
            options=list(self.pv_monitors.keys()),
        )
        self.selection.on_change("value", self.update_selection)
        self.build_plot()

    def build_plot(self) -> None:
        """
        Creates the plot object.
        """
        self.plot = figure(sizing_mode="scale_both", aspect_ratio=self._aspect_ratio)
        self.plot.line(x="x", y="y", line_width=2, source=self.source)
        self.plot.yaxis.axis_label = self.live_variable

        # as its scales, the plot uses all definedformats
        self.plot.xaxis.formatter = DatetimeTickFormatter(
            minutes="%H:%M:%S",
            minsec="%H:%M:%S",
            seconds="%H:%M:%S",
            microseconds="%H:%M:%S",
            milliseconds="%H:%M:%S",
        )

        self.plot.xaxis.major_label_orientation = "vertical"

        # add units to label
        if self.pv_monitors[self.live_variable].units:
            self.plot.yaxis.axis_label += (
                f" ({self.pv_monitors[self.live_variable].units})"
            )

        self.plot.xaxis.axis_label = "time (sec)"

    def update(self) -> None:
        """
        Callback to update the plot to reflect updated process variable values or to
        display a new process variable.


        """

        ts, ys = self.pv_monitors[self.live_variable].poll()
        if self._limit is not None and len(ts) > self._limit:
            ts = ts[-self._limit :]
            ys = ys[-self._limit :]

        self.source.data = dict(x=ts, y=ys)

    def update_selection(self, attr, old, new):
        """
        Bokeh callback for assigning new live process variable.
        """
        self.live_variable = new

    def _reset_values(self) -> None:
        """
        Callback for resetting values on reset button push.

        """
        self.pv_monitors[self.live_variable].reset()
