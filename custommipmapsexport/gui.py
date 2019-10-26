from functools import partial
import weakref
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets, QtUiTools, QtSvg

import sd

from .graphutils import find_package_of_graph, get_group_mapping, get_output_name

DEFAULT_ICON_SIZE = 24


def get_ui_manager():
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    ui_manager = app.getQtForPythonUIMgr()
    return ui_manager


class ExportDialog(QtCore.QObject):
    """ Handles all the events in the ui. """
    def __init__(self, ui_file, graphview_id, parent=None):
        super(ExportDialog, self).__init__(parent)
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly)
        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()
        
        self.__graph = get_ui_manager().getGraphFromGraphViewID(graphview_id)
        
        # State variables' defaults.
        self.destination_path = str(Path(self.get_pkg_path()).parent)
        self.unchecked_tree_items = list()  # list of uids.
        
        # Get references to widgets.
        self.dest_edit = self.window.findChild(QtWidgets.QLineEdit, 'edit_dest')
        self.combobox_comp = self.window.findChild(QtWidgets.QComboBox, 'comboBox_compression')
        self.edit_pattern = self.window.findChild(QtWidgets.QLineEdit, 'edit_pattern')
        self.pattern_preview = self.window.findChild(QtWidgets.QLabel, 'pattern_preview')
        self.tree = self.window.findChild(QtWidgets.QTreeWidget, 'tree')
        self.combobox_res = self.window.findChild(QtWidgets.QComboBox, 'comboBox_res')
        self.check_graph_res = self.window.findChild(QtWidgets.QCheckBox, 'check_graph_res')
        btn_browse = self.window.findChild(QtWidgets.QPushButton, 'btn_browse')
        btn_sel_all = self.window.findChild(QtWidgets.QPushButton, 'btn_sel_all')
        btn_sel_none = self.window.findChild(QtWidgets.QPushButton, 'btn_sel_none')
        btn_export = self.window.findChild(QtWidgets.QPushButton, 'btn_export')
        
        # Populate widgets with defaults.
        self.dest_edit.setText(self.destination_path)
        self.edit_pattern.setText("$(graph)_$(identifier)")
        self.populate_combobox_compression(self.combobox_comp)
        self.populate_combobox_resolution(self.combobox_res)
        
        # Connect widgets to actions.
        self.dest_edit.editingFinished.connect(self.on_destination_changed)
        self.edit_pattern.editingFinished.connect(self.on_pattern_changed)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.combobox_res.currentIndexChanged.connect(self.on_resolution_changed)
        btn_sel_all.clicked.connect(self.on_select_all)
        btn_sel_none.clicked.connect(self.on_select_none)
        btn_browse.clicked.connect(self.on_browse_destination)
        btn_export.clicked.connect(self.on_export)
    
    def show(self):
        self.tree.clear()
        self.populate_tree(self.tree)
        # If no outputs, show only warning.
        if self.tree.invisibleRootItem().childCount() == 0:
            self.show_warning("No Graph Outputs", "There is no output image to export from the selected graph.")
            return
        # Set the first output in the tree to be the current item.
        current_item = self.tree.invisibleRootItem().child(0).child(0)
        self.tree.setCurrentItem(current_item)
        self.on_pattern_changed()
        self.window.show()

    def show_warning(self, title, msg):
        ui_mgr = get_ui_manager()
        main_window = ui_mgr.getMainWindow()
        msg_box = QtWidgets.QMessageBox(parent=main_window)
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(msg)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec()
        
    def get_pkg_path(self):
        pkg = find_package_of_graph(self.__graph)
        path = pkg.getFilePath()
        return path
        
    def populate_tree(self, tree):
        # ToDo: Move default to top if present.
        groups = get_group_mapping(self.__graph)
        for group_name, ids in groups.items():
            group = QtWidgets.QTreeWidgetItem([group_name])
            items = list()
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
    
    def populate_combobox_compression(self, box):
        formats = [f"DXT{i}" for i in range(1, 6)]
        box.addItems(formats)
        
    def populate_combobox_resolution(self, box):
        for i in range(13, -1, -1):
            box.addItem(str(2**i), i)  # Set log2 as hidden value.
        box.setCurrentIndex(2)

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
        """ Rebuilds the unchecked items list.
        Inefficient method. But there aren't many calls expected.
        """
        self.unchecked_tree_items.clear()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.text(1) and not item.checkState(0):  # Exclude groups.
                self.unchecked_tree_items.append(item.text(1))
            next(iterator)
    
    def on_select_all(self):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, QtCore.Qt.Checked)
            next(iterator)
        self.unchecked_tree_items.clear()

    def on_select_none(self):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        self.unchecked_tree_items.clear()
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, QtCore.Qt.Unchecked)
            if item.text(1):  # Exclude groups.
                self.unchecked_tree_items.append(item.text(1))
            next(iterator)
        
    def on_resolution_changed(self):
        pass
    
    def on_destination_changed(self, path=None):
        if not path:
            self.destination_path = self.dest_edit.text()
        else:
            self.destination_path = path
            self.dest_edit.setText(path)
    
    def on_pattern_changed(self):
        """ Update the preview of the output name. """
        if not self.edit_pattern.text():
            self.edit_pattern.setText("$(identifier)")
        
        item = self.tree.currentItem()
        preview = get_output_name(self.__graph, item.text(1), self.edit_pattern.text())
        self.pattern_preview.setText(preview)
        
    def on_browse_destination(self):
        # Launch directory browser.
        path = QtWidgets.QFileDialog.getExistingDirectory(parent=self.window,
                                                          caption="Select output folder",
                                                          dir=self.destination_path)
        if path:
            self.on_destination_changed(path)
        
    def on_export(self):
        print("Export tab1 clicked.")


def load_svg_icon(icon_name, size):
    current_dir = Path(__file__).resolve().parent
    icon_file = current_dir / (icon_name + '.svg')

    svg_renderer = QtSvg.QSvgRenderer(icon_file)
    if svg_renderer.isValid():
        pixmap = QtGui.QPixmap(QtCore.QSize(size, size))

        if not pixmap.isNull():
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()

        return QtGui.QIcon(pixmap)

    return None
    
    
class MipMapExportGraphToolBar(QtWidgets.QToolBar):
    """ Toolbar to call the export ui dialog. """
    __toolbarList = {}
    
    def __init__(self, graphview_id, ui_manager):
        super(MipMapExportGraphToolBar, self).__init__(parent=ui_manager.getMainWindow())
        
        self.setObjectName('olafhaag.com.mipmap_export_toolbar')
        
        # Save the graphViewID and uiMgr for later use.
        self.__graphViewID = graphview_id
        self.__uiMgr = ui_manager
        # Load the UI from file.
        ui_file = Path(__file__).resolve().parent / "res/dialog.ui"

        self.dialog = self.load_ui(str(ui_file), parent=ui_manager.getMainWindow())
        
        # Add actions to our toolbar.
        act = self.addAction("MipMap Export")
        act.setToolTip("Save each resolution of the selected output as a MipMap level to a DDS file.")
        act.triggered.connect(self.dialog.show)
        
        self.__toolbarList[graphview_id] = weakref.ref(self)
        self.destroyed.connect(partial(MipMapExportGraphToolBar.__on_toolbar_deleted, graphview_id=graphview_id))
    
    def tooltip(self):
        return self.tr("MipMap Export Tools")
    
    def load_ui(self, filename, parent=None):
        """ Returns an instance of the exporter dialog. """
        ui = ExportDialog(filename, self.__graphViewID, parent)
        return ui
    
    @classmethod
    def __on_toolbar_deleted(cls, graphview_id):
        del cls.__toolbarList[graphview_id]
    
    @classmethod
    def remove_all_toolbars(cls):
        for toolbar in cls.__toolbarList.values():
            if toolbar():
                toolbar().deleteLater()


def on_new_graphview_created(graphview_id, ui_manager):
    # Create our toolbar.
    toolbar = MipMapExportGraphToolBar(graphview_id, ui_manager)
    
    # Add our toolbar to the graph widget.
    ui_manager.addToolbarToGraphView(
        graphview_id,
        toolbar,
        icon=None,
        tooltip="MipMap Export Toolbar")
