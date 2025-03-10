# Ignore attr-defined error for mypy that happen for Qt classes and widgets read from the UI file.
# mypy: disable-error-code="attr-defined"
import importlib.resources
import weakref
from functools import partial
from pathlib import Path
from typing import ClassVar

from PySide6 import QtCore, QtGui, QtSvg, QtUiTools, QtWidgets

import sd
from custommipmapsexport.graphutils import export_dds_files, find_package_of_graph, get_group_mapping, get_output_name
from sd.api.qtforpythonuimgrwrapper import QtForPythonUIMgrWrapper

DEFAULT_ICON_SIZE = 24


def get_ui_manager() -> QtForPythonUIMgrWrapper | None:
    """Get the UI Manager from the current context."""
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    return app.getQtForPythonUIMgr()


class ExportDialog(QtCore.QObject):
    """Handles all the events in the ui."""

    def __init__(self, ui_file: str, graphview_id: int, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        ui_qfile = QtCore.QFile(ui_file)
        ui_qfile.open(QtCore.QFile.ReadOnly)
        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        ui_qfile.close()

        ui_manager = get_ui_manager()
        if ui_manager is None:
            msg = "Failed to get UI Manager."
            raise RuntimeError(msg)
        self.__graph = ui_manager.getGraphFromGraphViewID(graphview_id)

        # State variables' defaults.
        self.destination_path = str(Path(self.get_pkg_path()).parent)
        self.unchecked_tree_items: list[str] = []  # list of uids.

        # Get references to widgets from tab1.
        self.dest_edit = self.window.findChild(QtWidgets.QLineEdit, "edit_dest")
        self.compression = self.window.findChild(QtWidgets.QComboBox, "comboBox_compression")
        self.pattern = self.window.findChild(QtWidgets.QLineEdit, "edit_pattern")
        self.pattern_preview = self.window.findChild(QtWidgets.QLabel, "pattern_preview")
        self.tree = self.window.findChild(QtWidgets.QTreeWidget, "tree")
        self.max_resolution = self.window.findChild(QtWidgets.QComboBox, "comboBox_res")
        self.use_graph_resolution = self.window.findChild(QtWidgets.QCheckBox, "check_graph_res")
        btn_browse = self.window.findChild(QtWidgets.QPushButton, "btn_browse")
        btn_sel_all = self.window.findChild(QtWidgets.QPushButton, "btn_sel_all")
        btn_sel_none = self.window.findChild(QtWidgets.QPushButton, "btn_sel_none")
        self.btn_export = self.window.findChild(QtWidgets.QPushButton, "btn_export")
        self.feedback = self.window.findChild(QtWidgets.QLabel, "feedback_label")

        # Get references to widgets from tab2.
        self.quality = self.window.findChild(QtWidgets.QSpinBox, "quality_spinBox")
        self.dxt_quality = self.window.findChild(QtWidgets.QComboBox, "dxt_quality_comboBox")
        self.generate_mipmaps = self.window.findChild(QtWidgets.QGroupBox, "mipsettings_groupBox")
        self.filter = self.window.findChild(QtWidgets.QComboBox, "mipfilter_comboBox")
        self.gamma = self.window.findChild(QtWidgets.QDoubleSpinBox, "gamma_spinBox")
        self.blur = self.window.findChild(QtWidgets.QDoubleSpinBox, "blur_spinBox")
        self.max_mip_lvls = self.window.findChild(QtWidgets.QSpinBox, "max_lvls_spinBox")
        self.wrap = self.window.findChild(QtWidgets.QCheckBox, "wrap_checkBox")
        self.btn_export_t2 = self.window.findChild(QtWidgets.QPushButton, "btn_export_t2")

        # Ensure all widgets are found in the dialog.
        widgets = [
            self.dest_edit,
            self.compression,
            self.pattern,
            self.pattern_preview,
            self.tree,
            self.max_resolution,
            self.use_graph_resolution,
            btn_browse,
            btn_sel_all,
            btn_sel_none,
            self.btn_export,
            self.feedback,
            self.quality,
            self.dxt_quality,
            self.generate_mipmaps,
            self.filter,
            self.gamma,
            self.blur,
            self.max_mip_lvls,
            self.wrap,
            self.btn_export_t2,
        ]
        for widget in widgets:
            if widget is None:
                msg = f"Failed to find widget in dialog.ui: {widget}"
                raise RuntimeError(msg)

        # Populate widgets with defaults. We already checked for None, so ignore the type checker.
        self.dest_edit.setText(self.destination_path)
        self.pattern.setText("$(graph)_$(identifier)")
        self.populate_compression(self.compression)
        self.populate_resolution(self.max_resolution)
        self.populate_dxt_quality()
        self.populate_filter()

        # Connect widgets to actions.
        self.dest_edit.editingFinished.connect(self.on_destination_changed)
        self.pattern.editingFinished.connect(self.on_pattern_changed)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        btn_sel_all.clicked.connect(self.on_select_all)
        btn_sel_none.clicked.connect(self.on_select_none)
        btn_browse.clicked.connect(self.on_browse_destination)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_export_t2.clicked.connect(self.on_export)

    def show(self):
        self.tree.clear()
        self.populate_tree(self.tree)
        # If no outputs, show only warning.
        if self.tree.invisibleRootItem().childCount() == 0:
            self.show_warning("No Graph Outputs", "There is no output image to export from the selected graph.")
            return

        # Find the first valid output item in the tree to set as the current item.
        current_item = None
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group.childCount() > 0:
                current_item = group.child(0)
                break

        if current_item is None:
            self.show_warning("No Valid Outputs", "There are no valid output images to export from the selected graph.")
            return
        self.tree.setCurrentItem(current_item)
        self.on_pattern_changed()
        self.feedback.setText("")
        self.window.show()

    def show_warning(self, title, msg):
        ui_mgr = get_ui_manager()
        main_window = ui_mgr.getMainWindow() if ui_mgr else None
        msg_box = QtWidgets.QMessageBox(parent=main_window)
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(msg)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec()

    def get_pkg_path(self):
        pkg = find_package_of_graph(self.__graph)
        return pkg.getFilePath()

    def populate_tree(self, tree):
        # ToDo: Move default to top if present.
        groups = get_group_mapping(self.__graph)
        for group_name, ids in groups.items():
            group = QtWidgets.QTreeWidgetItem([group_name])
            items = []
            for identifier, uid in ids:
                item = QtWidgets.QTreeWidgetItem([identifier])
                item.setData(1, QtCore.Qt.EditRole, uid)
                if uid in self.unchecked_tree_items:
                    item.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    item.setCheckState(0, QtCore.Qt.Checked)
                items.append(item)
            group.addChildren(items)
            tree.addTopLevelItem(group)
            group.setExpanded(True)
            self.update_group_checkstate(group)

    def populate_compression(self, box):
        formats = [
            "DXT1",
            "DXT2",
            "DXT3",
            "DXT4",
            "DXT5",
            "3DC",
            "DXN",
            "DXT5A",
            "DXT5_CCxY",
            "DXT5_xGxR",
            "DXT5_xGBR",
            "DXT5_AGBR",
            "DXT1A",
            "ETC1",
            "ETC2",
            "ETC2A",
            "ETC1S",
            "ETC2AS",
            "R8G8B8",
            "L8",
            "A8",
            "A8L8",
            "A8R8G8B",
        ]
        box.addItems(formats)

    def populate_resolution(self, box):
        for i in range(13, 1, -1):  # Minimum resolution in a block compression is 4x4.
            box.addItem(str(2**i), i)  # Set log2 as hidden value.
        box.setCurrentIndex(2)

    def populate_dxt_quality(self):
        options = ["superfast", "fast", "normal", "better", "uber"]
        self.dxt_quality.addItems(options)
        self.dxt_quality.setCurrentIndex(4)

    def populate_filter(self):
        options = ["box", "tent", "lanczos4", "mitchell", "kaiser"]
        self.filter.addItems(options)
        self.filter.setCurrentIndex(4)

    def on_tree_item_clicked(self, item):
        if self.tree.indexOfTopLevelItem(item) == -1:
            self.update_group_checkstate(item.parent())
            self.tree.setCurrentItem(item)
            self.on_pattern_changed()
        else:
            self.on_group_clicked(item)
        self.update_unchecked_items()

    def on_group_clicked(self, group):
        n_children = group.childCount()
        if group.checkState(0) == QtCore.Qt.Checked:
            new_state = QtCore.Qt.Checked
        elif group.checkState(0) == QtCore.Qt.Unchecked:
            new_state = QtCore.Qt.Unchecked
        else:  # Do nothing when partially checked.
            return

        for i in range(n_children):
            item = group.child(i)
            item.setCheckState(0, new_state)

    def update_group_checkstate(self, group):
        n_checked = 0
        n_children = group.childCount()
        for i in range(n_children):
            item = group.child(i)
            if item.checkState(0):
                n_checked += 1
        if n_checked == 0:
            group.setCheckState(0, QtCore.Qt.Unchecked)
        elif n_checked == n_children:
            group.setCheckState(0, QtCore.Qt.Checked)
        else:
            group.setCheckState(0, QtCore.Qt.PartiallyChecked)

    def update_unchecked_items(self):
        """Rebuilds the unchecked items list.

        Inefficient method. But there aren't many calls expected.
        """
        self.unchecked_tree_items.clear()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)  # type: ignore[call-overload]  # self.tree is not None.
        while iterator.value():
            item = iterator.value()
            if item.text(1) and not item.checkState(0):  # Exclude groups.
                self.unchecked_tree_items.append(item.text(1))
            next(iterator)

    def on_select_all(self):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)  # type: ignore[call-overload]  # self.tree is not None.
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, QtCore.Qt.Checked)
            next(iterator)
        self.unchecked_tree_items.clear()

    def on_select_none(self):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)  # type: ignore[call-overload]  # self.tree is not None.
        self.unchecked_tree_items.clear()
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, QtCore.Qt.Unchecked)
            if item.text(1):  # Exclude groups.
                self.unchecked_tree_items.append(item.text(1))
            next(iterator)

    def on_destination_changed(self, path=None):
        if not path:
            self.destination_path = self.dest_edit.text()
        else:
            self.destination_path = path
            self.dest_edit.setText(path)

    def on_pattern_changed(self):
        """Update the preview of the output name."""
        if not self.pattern.text():
            self.pattern.setText("$(identifier)")

        item = self.tree.currentItem()
        preview = get_output_name(self.__graph, item.text(1), self.pattern.text())
        self.pattern_preview.setText(preview)

    def on_browse_destination(self):
        if path := QtWidgets.QFileDialog.getExistingDirectory(
            parent=self.window,
            caption="Select output folder",
            dir=self.destination_path,
        ):
            self.on_destination_changed(path)

    def get_checked_output_uids(self) -> list[str]:
        """Get the list of checked output IDs.

        :return: List of checked output IDs.
        """
        checked_outputs = []
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)  # type: ignore[call-overload]  # self.tree is not None.
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == QtCore.Qt.Checked and item.text(1):  # Exclude groups.
                checked_outputs.append(item.text(1))
            next(iterator)
        return checked_outputs

    def get_advanced_settings(self):
        settings = {"-quality": str(self.quality.value())}
        settings["-dxtQuality"] = self.dxt_quality.currentText()
        if self.generate_mipmaps.isChecked():
            settings["-mipFilter"] = self.filter.currentText()
            settings["-gamma"] = str(self.gamma.value())
            settings["-blurriness"] = str(self.blur.value())
            settings["-maxmips"] = str(self.max_mip_lvls.value())
            if self.wrap.isChecked():
                settings["-wrap"] = ""
        else:
            settings["-mipMode"] = "None"
        return settings

    def on_export(self):
        if output_uids := self.get_checked_output_uids():
            # Disable export buttons while processing.
            self.btn_export.setEnabled(False)
            self.btn_export_t2.setEnabled(False)

            compression = self.compression.currentText().lower()
            if not self.use_graph_resolution.isChecked():
                max_res = self.max_resolution.itemData(self.max_resolution.currentIndex())
            else:
                max_res = None

            adv_settings = self.get_advanced_settings()

            self.feedback.setText("Exporting...")
            result = export_dds_files(
                self.__graph,
                output_uids,
                self.destination_path,
                self.pattern.text(),
                compression,
                max_resolution=max_res,
                custom_lvls=False,
                **adv_settings,
            )
            self.feedback.setText(result)
            # Enable Export buttons.
            self.btn_export.setEnabled(True)
            self.btn_export_t2.setEnabled(True)


def load_svg_icon(icon_name: str, size: int) -> QtGui.QIcon | None:
    """Load an SVG icon from the resources.

    :param icon_name: name of the icon to load.
    :param size: size of the icon.
    :return: QtGui.QIcon object or None if the icon could not be loaded.
    """
    icon_file = importlib.resources.files("custommipmapsexport.res").joinpath(f"{icon_name}.svg")

    svg_renderer = QtSvg.QSvgRenderer(str(icon_file))
    if svg_renderer.isValid():
        pixmap = QtGui.QPixmap(QtCore.QSize(size, size))

        if not pixmap.isNull():
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()

        return QtGui.QIcon(pixmap)

    return None


class MipmapExportGraphToolBar(QtWidgets.QToolBar):
    """Toolbar to call the export ui dialog."""

    __toolbarList: ClassVar[dict[int, weakref.ReferenceType["MipmapExportGraphToolBar"]]] = {}

    def __init__(self, graphview_id: int, ui_manager: QtForPythonUIMgrWrapper):
        super().__init__(parent=ui_manager.getMainWindow())

        self.setObjectName("olafhaag.com.mipmap_export_toolbar")

        # Save the graphViewID for later use.
        self.__graphViewID = graphview_id
        # Load the UI from file.
        ui_file = importlib.resources.files("custommipmapsexport.res").joinpath("dialog.ui")

        self.dialog = self.load_ui(str(ui_file), parent=ui_manager.getMainWindow())

        # Add actions to our toolbar.
        export_icon_name = "mipmapexport"
        export_icon = load_svg_icon(export_icon_name, DEFAULT_ICON_SIZE)
        if export_icon is None:
            msg = f"Failed to load export icon {export_icon_name} into toolbar."
            raise RuntimeError(msg)
        act = self.addAction(export_icon, "Export Custom Mipmaps")
        act.setToolTip("Export outputs to compressed DDS files with mipmaps.")
        act.triggered.connect(self.dialog.show)

        self.__toolbarList[graphview_id] = weakref.ref(self)
        self.destroyed.connect(partial(MipmapExportGraphToolBar.__on_toolbar_deleted, graphview_id=graphview_id))

    def tooltip(self):
        return self.tr("Mipmap Tools")

    def load_ui(self, filename: str, parent: QtWidgets.QMainWindow | None = None) -> ExportDialog:
        """Return an instance of the exporter dialog."""
        return ExportDialog(filename, self.__graphViewID, parent)

    @classmethod
    def __on_toolbar_deleted(cls, graphview_id: int):
        del cls.__toolbarList[graphview_id]

    @classmethod
    def remove_all_toolbars(cls):
        for toolbar in cls.__toolbarList.values():
            if ref := toolbar():
                ref.deleteLater()


def on_new_graphview_created(graphview_id: int, ui_manager: QtForPythonUIMgrWrapper) -> None:
    """Create a new toolbar and adds it to the graph view when a new graph view is created."""
    # Create our toolbar.
    toolbar = MipmapExportGraphToolBar(graphview_id, ui_manager)

    # Add our toolbar to the graph widget.
    ui_manager.addToolbarToGraphView(
        graphview_id, toolbar, icon=load_svg_icon("mipmaptools", DEFAULT_ICON_SIZE), tooltip=toolbar.tooltip()
    )
