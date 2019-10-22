from functools import partial
import weakref
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets, QtUiTools, QtSvg

import sd

DEFAULT_ICON_SIZE = 24


def get_ui_manager():
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    ui_manager = app.getQtForPythonUIMgr()
    return ui_manager


class ExportDialog(QtCore.QObject):
    """ Handles all the events in the ui. """
    def __init__(self, ui_file, parent=None):
        super(ExportDialog, self).__init__(parent)
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly)
        
        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()
        
        # State variables' defaults.
        self.destination_path = str(Path.cwd())  # ToDo: Get package path from some graphutils func.
        
        # Get references to widgets.
        self.dest_edit_tab1 = self.window.findChild(QtWidgets.QLineEdit, 'edit_dest_t1')
        self.edit_pattern_t1 = self.window.findChild(QtWidgets.QLineEdit, 'edit_pattern_t1')
        self.pattern_preview_t1 = self.window.findChild(QtWidgets.QLabel, 'pattern_preview_t1')
        self.tree_view_t1 = self.window.findChild(QtWidgets.QTreeView, 'tree_view_t1')
        self.combobox_res_t1 = self.window.findChild(QtWidgets.QCheckBox, 'comboBox_res')
        self.check_graph_res_t1 = self.window.findChild(QtWidgets.QCheckBox, 'check_graph_res')
        btn_browse_t1 = self.window.findChild(QtWidgets.QPushButton, 'btn_browse_t1')
        btn_sel_all_t1 = self.window.findChild(QtWidgets.QPushButton, 'btn_sel_all_t1')
        btn_sel_none_t1 = self.window.findChild(QtWidgets.QPushButton, 'btn_sel_none_t1')
        btn_export_t1 = self.window.findChild(QtWidgets.QPushButton, 'btn_export_t1')
        
        # Populate widgets with defaults.
        self.dest_edit_tab1.setText(self.destination_path)
        self.populate_combobox(self.combobox_res_t1)
        
        # Connect widgets to actions.
        self.dest_edit_tab1.editingFinished.connect(self.update_destination)
        self.edit_pattern_t1.editingFinished.connect(self.update_pattern)
        btn_sel_all_t1.clicked.connect(self.select_all_handler_tab1())
        btn_sel_none_t1.clicked.connect(self.select_none_handler_tab1())
        btn_browse_t1.clicked.connect(self.browse_handler_tab1)
        btn_export_t1.clicked.connect(self.export_tab1_handler)
    
    def show(self):
        # Todo: populate tree view.
        self.window.show()
        
    def populate_combobox(self, box):
        pass
    
    def update_destination(self, path=None):
        if not path:
            self.destination_path = self.dest_edit_tab1.text()
        else:
            self.destination_path = path
            self.dest_edit_tab1.setText(path)
    
    def update_pattern(self):
        # ToDo: regex
        # ToDo: update preview
        pass
    
    def select_all_handler_tab1(self):
        print('Select all button clicked')
    
    def select_none_handler_tab1(self):
        print('Select none button clicked')
        
    def browse_handler_tab1(self):
        # Launch directory browser.
        path = QtWidgets.QFileDialog.getExistingDirectory(parent=self.window,
                                                          caption="Select output folder",
                                                          dir=self.destination_path)
        if path:
            self.update_destination(path)
        
    def export_tab1_handler(self):
        print('Export tab1 clicked.')


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
        ui = ExportDialog(filename, parent)
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
