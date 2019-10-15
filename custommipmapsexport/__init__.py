from functools import partial

# Designer imports
import sd


from .gui import MipMapExportGraphToolBar, on_new_graphview_created


def get_ui_manager():
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    ui_manager = app.getQtForPythonUIMgr()
    return ui_manager


#
# Plugin entry points.
#
graphview_created_callback_id = 0


def initializeSDPlugin():
    # We need a way to unregister the callback for the toolbar.
    
    # Get the UI manager object.
    ui_manager = get_ui_manager()
    
    if ui_manager:
        global graphview_created_callback_id
        # Register a callback to know when GraphViews are created. Creates the toolbar.
        graphview_created_callback_id = ui_manager.registerGraphViewCreatedCallback(partial(on_new_graphview_created,
                                                                                            ui_manager=ui_manager))
        print("MipMap Export Plugin initialized.\n"
              "Toolbar will be attached to newly opened graph views.")


def uninitializeSDPlugin():
    # Get the UI manager object.
    ui_manager = get_ui_manager()
    if ui_manager:
        global graphview_created_callback_id
        ui_manager.unregisterCallback(graphview_created_callback_id)
        MipMapExportGraphToolBar.remove_all_toolbars()
    
    print("MipMap Export Plugin unloaded.")
