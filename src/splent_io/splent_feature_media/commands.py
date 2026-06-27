"""
CLI commands contributed by splent_feature_media.

These commands are auto-discovered by the framework and exposed in the
SPLENT CLI under the ``feature:media`` group.

Usage::

    splent feature:media hello
"""

import click


@click.command("hello")
def hello():
    """Example command — replace with your own."""
    click.echo("  Hello from splent_feature_media!")


cli_commands = [hello]
