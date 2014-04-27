import os
import sys

def open_os(filepath):
    """
    Opens the specified file using the devices default handler.

    :filepath    String representing the path to the file
    :return      None
    """
    if sys.platform.startswith('linux'):
        subprocess.call(['xdg-open', filepath])
    elif sys.platform.startswith('darwin'):
        subprocess.call(['open', filepath])
    else:
        os.startfile(filepath)
