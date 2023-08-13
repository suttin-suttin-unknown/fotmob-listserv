import click

from pprint import pprint

from api import FotmobAPI

api = None

class YesNoParamType(click.ParamType):
    name = "yes or no"

    def convert(self, value, param, ctx):
        if value.lower() not in ("y", "n", "yes", "no"):
            self.fail(f"Invalid choice: {value}. Use 'y' or 'n'.", param, ctx)
        return value.lower() in ("y", "yes")


@click.group()
def cli():
    """
    Cli tool for managing player data entry.
    """
    pass


@cli.command()
@click.argument("search_term", required=True)
def add_player(term):
    """
    Add player to watchlist.
    """
    results = api.search(term)

    if not results:
        click.echo(f"Search term {term} returned no results.")

    else:
        choice = None
        if len(results) > 1:
            click.echo(f"Multiple results. Please select an option: ")
            for i, result in enumerate(results, start=1):
                name, _ = result
                click.echo(f"{i}: {name}")

            while True:
                choice_number = int(click.prompt("Your choice"))
                try:
                    choice = results[choice_number - 1]
                    break
                except IndexError:
                    click.echo(f"Invalid choice {choice}. Please enter a valid choice.")

            name, player_id = choice
            click.echo(f"You have chosen {name} ({player_id})")

        else:
            name, player_id = results[0]
            choice = click.prompt(f"One player found: '{name}'. Select player? (y/n)", type=YesNoParamType())
            if choice:
                click.echo(f"You have chosen {name} ({player_id})")
            else:
                click.echo(f"Player not selected.")


@cli.command
@click.argument("league_id")
def get_league_transfers(league_id):
    """
    Get recent transfers from league.
    """
    results = api.get_league(league_id, tab="transfers")
    pprint(results)



if __name__ == '__main__':
    # Use singleton for API.
    api = FotmobAPI()
    cli()
