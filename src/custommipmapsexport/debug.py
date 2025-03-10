"""This module is only for debugging purposes and should not be used in production.

Alert: The debugpy.listen() method may let anyone who can connect to the specified port
execute arbitrary code within the debugged process.
Therefore, debugging should only be set up and performed on secure networks.

Launch the application, open the Python Editor and run the following code.
Then in VSCode, select Run & Debug and select the
'Python: Attach to Substance 3D Designer' configuration and click on Start Debugging.
"""

import sys

debugpy_path = "/path/to/debugpy/module"
debugpy_port = 5678
designer_py_interpreter = "/path/to/python/executable/bundled/in/designer"

if debugpy_path not in sys.path:
    sys.path.append(debugpy_path)

import debugpy  # noqa: E402, T100

debugpy.configure(python=designer_py_interpreter)
debugpy.listen(debugpy_port)  # noqa: T100
