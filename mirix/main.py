import os
import sys
import traceback

import questionary
import requests
import typer
from rich.console import Console

import mirix.agent as agent
import mirix.errors as errors
import mirix.system as system

# import benchmark
from mirix import create_client
from mirix.benchmark.benchmark import bench
from mirix.cli.cli import delete_agent, open_folder, run, server, version
from mirix.cli.cli_config import add, add_tool, configure, delete, list, list_tools
from mirix.cli.cli_load import app as load_app
from mirix.config import MirixConfig
from mirix.constants import FUNC_FAILED_HEARTBEAT_MESSAGE, REQ_HEARTBEAT_MESSAGE

# from mirix.interface import CLIInterface as interface  # for printing to terminal
from mirix.streaming_interface import AgentRefreshStreamingInterface

# interface = interface()

# disable composio print on exit
os.environ["COMPOSIO_DISABLE_VERSION_CHECK"] = "true"

app = typer.Typer(pretty_exceptions_enable=False)
app.command(name="run")(run)
app.command(name="version")(version)
app.command(name="configure")(configure)
app.command(name="list")(list)
app.command(name="add")(add)
app.command(name="add-tool")(add_tool)
app.command(name="list-tools")(list_tools)
app.command(name="delete")(delete)
app.command(name="server")(server)
app.command(name="folder")(open_folder)
# load data commands
app.add_typer(load_app, name="load")
# benchmark command
app.command(name="benchmark")(bench)
# delete agents
app.command(name="delete-agent")(delete_agent)


def clear_line(console, strip_ui=False):
    if strip_ui:
        return
    if os.name == "nt":  # for windows
        console.print("\033[A\033[K", end="")
    else:  # for linux
        sys.stdout.write("\033[2K\033[G")
        sys.stdout.flush()


def run_agent_loop(
    mirix_agent: agent.Agent,
    config: MirixConfig,
    first: bool,
    no_verify: bool = False,
    strip_ui: bool = False,
    stream: bool = False,
):
    if isinstance(mirix_agent.interface, AgentRefreshStreamingInterface):
        # mirix_agent.interface.toggle_streaming(on=stream)
        if not stream:
            mirix_agent.interface = mirix_agent.interface.nonstreaming_interface

    if hasattr(mirix_agent.interface, "console"):
        console = mirix_agent.interface.console
    else:
        console = Console()

    counter = 0
    user_input = None
    skip_next_user_input = False
    user_message = None
    USER_GOES_FIRST = first

    if not USER_GOES_FIRST:
        console.input("[bold cyan]Hit enter to begin (will request first Mirix message)[/bold cyan]\n")
        clear_line(console, strip_ui=strip_ui)
        print()

    multiline_input = False

    # create client
    client = create_client()

    # run loops
    while True:
        if not skip_next_user_input and (counter > 0 or USER_GOES_FIRST):
            # Ask for user input
            if not stream:
                print()
            user_input = questionary.text(
                "Enter your message:",
                multiline=multiline_input,
                qmark=">",
            ).ask()
            clear_line(console, strip_ui=strip_ui)
            if not stream:
                print()

            # Gracefully exit on Ctrl-C/D
            if user_input is None:
                user_input = "/exit"

            user_input = user_input.rstrip()

            if user_input.startswith("!"):
                print(f"Commands for CLI begin with '/' not '!'")
                continue

            if user_input == "":
                # no empty messages allowed
                print("Empty input received. Try again!")
                continue

            # Handle CLI commands
            # Commands to not get passed as input to Mirix
            if user_input.startswith("/"):
                # updated agent save functions
                if user_input.lower() == "/exit":
                    # mirix_agent.save()
                    agent.save_agent(mirix_agent)
                    break
                elif user_input.lower() == "/save" or user_input.lower() == "/savechat":
                    # mirix_agent.save()
                    agent.save_agent(mirix_agent)
                    continue
                
                elif user_input.lower() == "/dump" or user_input.lower().startswith("/dump "):
                    # Check if there's an additional argument that's an integer
                    command = user_input.strip().split()
                    amount = int(command[1]) if len(command) > 1 and command[1].isdigit() else 0
                    if amount == 0:
                        mirix_agent.interface.print_messages(mirix_agent._messages, dump=True)
                    else:
                        mirix_agent.interface.print_messages(mirix_agent._messages[-min(amount, len(mirix_agent.messages)) :], dump=True)
                    continue

                elif user_input.lower() == "/dumpraw":
                    mirix_agent.interface.print_messages_raw(mirix_agent._messages)
                    continue

                elif user_input.lower() == "/memory":
                    print(f"\nDumping memory contents:\n")
                    print(f"{mirix_agent.agent_state.memory.compile()}")
                    print(f"{mirix_agent.archival_memory.compile()}")
                    continue

                elif user_input.lower() == "/model":
                    print(f"Current model: {mirix_agent.agent_state.llm_config.model}")
                    continue

                elif user_input.lower() == "/summarize":
                    try:
                        mirix_agent.summarize_messages_inplace()
                        typer.secho(
                            f"/summarize succeeded",
                            fg=typer.colors.GREEN,
                            bold=True,
                        )
                    except (errors.LLMError, requests.exceptions.HTTPError) as e:
                        typer.secho(
                            f"/summarize failed:\n{e}",
                            fg=typer.colors.RED,
                            bold=True,
                        )
                    continue

                elif user_input.lower() == "/tokens":
                    tokens = mirix_agent.count_tokens()
                    typer.secho(
                        f"{tokens}/{mirix_agent.agent_state.llm_config.context_window}",
                        fg=typer.colors.GREEN,
                        bold=True,
                    )
                    continue

                elif user_input.lower().startswith("/add_function"):
                    try:
                        if len(user_input) < len("/add_function "):
                            print("Missing function name after the command")
                            continue
                        function_name = user_input[len("/add_function ") :].strip()
                        result = mirix_agent.add_function(function_name)
                        typer.secho(
                            f"/add_function succeeded: {result}",
                            fg=typer.colors.GREEN,
                            bold=True,
                        )
                    except ValueError as e:
                        typer.secho(
                            f"/add_function failed:\n{e}",
                            fg=typer.colors.RED,
                            bold=True,
                        )
                        continue
                elif user_input.lower().startswith("/remove_function"):
                    try:
                        if len(user_input) < len("/remove_function "):
                            print("Missing function name after the command")
                            continue
                        function_name = user_input[len("/remove_function ") :].strip()
                        result = mirix_agent.remove_function(function_name)
                        typer.secho(
                            f"/remove_function succeeded: {result}",
                            fg=typer.colors.GREEN,
                            bold=True,
                        )
                    except ValueError as e:
                        typer.secho(
                            f"/remove_function failed:\n{e}",
                            fg=typer.colors.RED,
                            bold=True,
                        )
                        continue

                # No skip options
                elif user_input.lower() == "/wipe":
                    mirix_agent = agent.Agent(mirix_agent.interface)
                    user_message = None

                elif user_input.lower() == "/heartbeat":
                    user_message = system.get_heartbeat()

                elif user_input.lower() == "/memorywarning":
                    user_message = system.get_token_limit_warning()

                elif user_input.lower() == "//":
                    multiline_input = not multiline_input
                    continue

                elif user_input.lower() == "/" or user_input.lower() == "/help":
                    questionary.print("CLI commands", "bold")
                    for cmd, desc in USER_COMMANDS:
                        questionary.print(cmd, "bold")
                        questionary.print(f" {desc}")
                    continue
                else:
                    print(f"Unrecognized command: {user_input}")
                    continue

            else:
                # If message did not begin with command prefix, pass inputs to Mirix
                # Handle user message and append to messages
                user_message = str(user_input)

        skip_next_user_input = False

        def process_agent_step(user_message, no_verify):
            # TODO(charles): update to use agent.step() instead of inner_step()

            if user_message is None:
                step_response = mirix_agent.inner_step(
                    messages=[],
                    first_message=False,
                    skip_verify=no_verify,
                    stream=stream,
                )
            else:
                step_response = mirix_agent.step_user_message(
                    user_message_str=user_message,
                    first_message=False,
                    skip_verify=no_verify,
                    stream=stream,
                )
            new_messages = step_response.messages
            heartbeat_request = step_response.heartbeat_request
            function_failed = step_response.function_failed
            token_warning = step_response.in_context_memory_warning
            step_response.usage

            agent.save_agent(mirix_agent)
            skip_next_user_input = False
            if token_warning:
                user_message = system.get_token_limit_warning()
                skip_next_user_input = True
            elif function_failed:
                user_message = system.get_heartbeat(FUNC_FAILED_HEARTBEAT_MESSAGE)
                skip_next_user_input = True
            elif heartbeat_request:
                user_message = system.get_heartbeat(REQ_HEARTBEAT_MESSAGE)
                skip_next_user_input = True

            return new_messages, user_message, skip_next_user_input

        while True:
            try:
                if strip_ui:
                    _, user_message, skip_next_user_input = process_agent_step(user_message, no_verify)
                    break
                else:
                    if stream:
                        # Don't display the "Thinking..." if streaming
                        _, user_message, skip_next_user_input = process_agent_step(user_message, no_verify)
                    else:
                        with console.status("[bold cyan]Thinking...") as status:
                            _, user_message, skip_next_user_input = process_agent_step(user_message, no_verify)
                    break
            except KeyboardInterrupt:
                print("User interrupt occurred.")
                retry = questionary.confirm("Retry agent.step()?").ask()
                if not retry:
                    break
            except Exception:
                print("An exception occurred when running agent.step(): ")
                traceback.print_exc()
                retry = questionary.confirm("Retry agent.step()?").ask()
                if not retry:
                    break

        counter += 1

    print("Finished.")


USER_COMMANDS = [
    ("//", "toggle multiline input mode"),
    ("/exit", "exit the CLI"),
    ("/save", "save a checkpoint of the current agent/conversation state"),
    ("/load", "load a saved checkpoint"),
    ("/dump <count>", "view the last <count> messages (all if <count> is omitted)"),
    ("/memory", "print the current contents of agent memory"),
    ("/pop <count>", "undo <count> messages in the conversation (default is 3)"),
    ("/retry", "pops the last answer and tries to get another one"),
    ("/rethink <text>", "changes the inner thoughts of the last agent message"),
    ("/rewrite <text>", "changes the reply of the last agent message"),
    ("/heartbeat", "send a heartbeat system message to the agent"),
    ("/memorywarning", "send a memory warning system message to the agent"),
    ("/attach", "attach data source to agent"),
]
