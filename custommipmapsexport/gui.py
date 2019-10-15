from functools import partial
import weakref
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets, QtUiTools, QtSvg


DEFAULT_ICON_SIZE = 24


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
        """
        Loads a Qt Designer .ui file.
        Returns a widget.
        """
        loader = QtUiTools.QUiLoader()
        ui_file = QtCore.QFile(filename)
        ui_file.open(QtCore.QFile.ReadOnly)
        ui = loader.load(ui_file, parent)
        ui_file.close()
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
