from functools import partial

from custommipmapsexport.gui import MipmapExportGraphToolBar, get_ui_manager, on_new_graphview_created
from custommipmapsexport.logger import logger


class MipmapExportPlugin:
    """State handler for the Mipmap Export Plugin."""

    # States we need to keep track of for registering/unregistering.
    graphview_created_callback_id: int = 0

    @classmethod
    def initialize(cls) -> None:
        """Initialize the Mipmap Export Plugin."""
        if ui_manager := get_ui_manager():
            # Register a callback to know when GraphViews are created. Creates the toolbar.
            cls.graphview_created_callback_id = ui_manager.registerGraphViewCreatedCallback(
                partial(on_new_graphview_created, ui_manager=ui_manager)
            )
            logger.info("Mipmap Export Plugin initialized.\nToolbar will be attached to newly opened graph views.")

    @classmethod
    def uninitialize(cls) -> None:
        """Uninitialize the Mipmap Export Plugin."""
        if ui_manager := get_ui_manager():
            ui_manager.unregisterCallback(cls.graphview_created_callback_id)
            MipmapExportGraphToolBar.remove_all_toolbars()

        logger.info("Mipmap Export Plugin unloaded.")


#
# Plugin entry points.
#
def initializeSDPlugin() -> None:  # noqa: N802  # Predefined names from the API.
    """
    Initialize the Mipmap Export Plugin.

    This function is called when the plugin is loaded."
    """
    MipmapExportPlugin.initialize()


def uninitializeSDPlugin() -> None:  # noqa: N802  # Predefined names from the API.
    """
    Uninitialize the Mipmap Export Plugin.

    This function is called when the plugin is unloaded.
    """
    MipmapExportPlugin.uninitialize()
