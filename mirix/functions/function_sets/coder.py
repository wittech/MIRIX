from typing import Optional

from mirix.agent import Agent

def bash(self: "Agent", command: str) -> Optional[str]:
    """
    Runs the given command directly in bash.

    Args:
        command (str): A command to run directly in the current shell.
    
    Returns:
        Output from bash.
    """
    return None

def str_replace_editor(self: "Agent", command: str, path: str, file_text: str=None, view_range: str=None, old_str: str=None, new_str: str=None, insert_line: int=None) -> Optional[str]:
    """
    Custom editing tool for viewing, creating and editing files
    * State is persistent across command calls and discussions with the user 
    * If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep 
    * The `create` command cannot be used if the specified `path` already exists as a file 
    * If a `command` generates a long output, it will be truncated and marked with `<response clipped>` 
    * The `undo_edit` command will revert the last edit made to the file at `path`. 
    
    Notes for using the `str_replace` command: 
    * The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces! 
    * If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique 
    * The `new_str` parameter should contain the edited lines that should replace the `old_str`.

    Args:
        command (str): The commands to run. Allowed options are: `view` (requires 'path'), `create` (requires 'path' and 'file_text'), `str_replace` (requires 'path', 'old_str' and 'new_str'), `insert` (requires 'path', 'insert_line' and 'new_str'), `undo_edit` (requires 'path'). 
        path (str): Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.
        file_text (str): Content of the file to be created.
        view_range (array): Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.
        old_str (str): Containing the string in `path` to replace.
        new_str (str): Containing the new string. 
        insert_line (int): The `new_str` will be inserted AFTER the line `insert_line` of `path`.

    Returns:
        str: Output from the command.
    """

    return None

def submit(self: "Agent") -> Optional[str]:
    """
    Submits the current file

    Args:
        None
    Returns:
        None
    """


def screen_shot(self: "Agent", local_url: str) -> Optional[str]:
    """
    Take a screenshot of the current screen.

    Args:
        local_url (str): The local URL of the screen to take a screenshot of.

    Returns:
        output_path[str]: the path to the screenshot image.
    """
    output_path = self.interface.screen_shot()
    return output_path
