#!/usr/bin/env python

import sys
import os
import platform
import json
from pathlib import Path

import click
from click_repl import repl
from prompt_toolkit.history import FileHistory
import requests
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers import get_lexer_by_name

from wizclientpy.sync.api import (
    AccountsServerApi, KnowledgeBaseServerApi)
from wizclientpy.sync.api import WIZNOTE_ACOUNT_SERVER
from wizclientpy.sync.token import WizToken
from wizclientpy.constants import WIZNOTE_HOME_DIR, WIZNOTE_HOME
from wizclientpy.errors import InvalidUser, InvalidPassword
from wizclientpy.utils.msgtools import error, warning, success
from wizclientpy.cmd.db import db


@click.group(invoke_without_command=True)
@click.pass_context
def wizcli(ctx):
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None:
        ctx.invoke(shell)


@wizcli.command()
@click.pass_context
@click.option("--user-id", prompt="User Name",
              help="Account name of your WizNote.")
@click.option("--password", prompt="Password", hide_input=True,
              help="Password of you WizNote account. WARNING: To avoid"
              " password being recorded in bash commandline history, this"
              " option should not be used in production.")
@click.option("-s", "--server", help="Set address of your account server."
              " Server address can be a pure IP address or prefixed with http"
              " or https schema.", default=WIZNOTE_ACOUNT_SERVER)
def login(ctx, user_id, password, server):
    """
    Login to WizNote server.
    """
    token = WizToken(server, user_id, password)
    try:
        user_info = token.login()
    except InvalidUser:
        click.echo(error("User `%s` does not exist!" % user_id))
    except InvalidPassword:
        click.echo(error("Password of `%s` is not correct!" % user_id))
    else:
        ctx.obj["token"] = token
        ctx.obj["user_info"] = user_info
        # Greetings
        click.echo(success("Hello '{name}'".format(
            name=user_info.strDisplayName)))


wizcli.add_command(db)


@wizcli.command()
@click.argument("keys", nargs=-1)
@click.pass_context
def user(ctx, keys):
    """
    Show user information.

    You can query the value of a given KEYS.
    """
    info = ctx.obj["user_info"]
    if keys:
        for key in keys:
            if key in dir(info):
                click.echo(getattr(info, key))
    else:
        strInfo = str(info)
        lexer = get_lexer_by_name("ini")
        formatter = TerminalFormatter()
        click.echo(highlight(strInfo, lexer, formatter))


@wizcli.command()
def shell():
    """
    Open an interactive tools, just like a shell.
    """
    prompt_kwargs = {
        'history': FileHistory(
            str(Path(WIZNOTE_HOME).joinpath(".wizcli_history"))),
        'message': u"wizcli>>> "}
    repl(click.get_current_context(), prompt_kwargs=prompt_kwargs)


if __name__ == '__main__':
    # TODO: It's important to deal with Ctrl+C interrupt when writing database.
    wizcli(obj={})
