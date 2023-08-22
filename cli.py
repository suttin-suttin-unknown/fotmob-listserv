import ast
import click
from collections import defaultdict

from fotmoblistserv.api import API
from fotmoblistserv.objects import League, Player, Team, Transfer


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
@click.argument("league_id", required=True)
@click.option("-n", "--num-apps", type=click.INT, default=None)
def get_all_totw_players(league_id, num_apps):
    league = League(league_id)
    count = 1
    totws = []
    while True:
        try:
            totw = league.get_totw_for_week(week=count)["players"]
            totws.extend(totw)
            count += 1
        except ValueError:
            break

    player_groupings = defaultdict(list)
    for player in totws:
        player_groupings[player["participantId"]].append(player)
    
    player_groupings = dict(player_groupings)
    if num_apps:
        player_groupings = dict([(k, v) for k, v in player_groupings.items() if len(v) >= num_apps])

    count = 0
    for (player_id, data) in sorted(player_groupings.items(), key=lambda v: -len(v[-1])):
        if len(data) != count:
            count = len(data)
            click.echo(f"\n{count}\n")
        name = data[0]["name"]
        player_id = data[0]["participantId"]
        ratings = [str(d["rating"]) for d in data]
        click.echo(f"{name} ({player_id}): {', '.join(ratings)}")


@cli.command()
@click.argument("league_id", required=True)
@click.argument("round_id", required=False)
def get_totw(league_id, round_id):
    league = League(league_id)

    try:
        if round_id:
            totw = league.get_totw_for_week(week=round_id)
        else:
            totw = league.get_totw_for_week()
    except ValueError as error:
        click.echo(error)
        return
    
    s = f"{league.get_name()} TOTW (Week {totw['players'][0]['roundNumber']})\n"
    banner = "\n" + "=" * len(s) + "\n"

    click.echo(banner)
    click.echo(s)
    for player in totw["players"]:
        msg = f"{player['name']} - {player['rating']}"
        if player["motm"] == 1:
            msg = " ".join([msg, "(MOTM)"])
        click.echo(msg)
    click.echo(banner)


@cli.command()
@click.argument("search_term", required=True)
def add_player(search_term):
    """
    Add player to watchlist.
    """
    api = API()
    results = api.search(search_term)

    if not results:
        click.echo(f"Search search_term {search_term} returned no results.")
    else:
        results = [result["options"] for result in results["squadMemberSuggest"]][0]
        choice = None

        if len(results) > 1:
            click.echo(f"Multiple results. Please select an option: ")
            for i, result in enumerate(results, start=1):
                name, fm_id = result["text"].split("|")
                print(f"{i}: {name} ({fm_id})")

            while True:
                choice_number = int(click.prompt("Your choice"))
                try:
                    choice = results[choice_number - 1]
                    break
                except IndexError:
                    click.echo(f"Invalid choice {choice}. Please enter a valid choice.")

            name, fm_id = choice["text"].split("|")

        elif len(results) == 1:
            choice = results[0]
            name, fm_id = choice["text"].split("|")

        player = Player(fm_id)
        player.save()
        click.echo(f"Player {player._id} {player} saved.")


@cli.command()
@click.argument("team_id", required=True)
@click.option("-i", "--transfers-in", type=click.BOOL, default=True)
@click.option("-o", "--transfers-out", type=click.BOOL, default=False)
@click.option("-l", "--on-loan", type=click.BOOL, default=False)
@click.option("-e", "--contract-extension", type=click.BOOL, default=False)
def get_transfers(team_id, transfers_in, transfers_out, on_loan, contract_extension):
    team = Team(team_id)
    click.echo(f"{team.get_name()}\n")

    transfers = list(Transfer.get_transfers_from_team(team))

    transfer_list = []
    in_list = []
    out_list = []
    if transfers_in:
        in_list = [t for t in transfers if int(t.to_club_id) == int(team._id)]
        if not on_loan:
            in_list = [t for t in in_list if not t.on_loan]

        if not contract_extension:
            in_list = [t for t in in_list if not t.contract_extension]

    if transfers_out:
        out_list = [t for t in transfers if int(t.from_club_id) == int(team._id)]
        if not on_loan:
            out_list = [t for t in out_list if not t.on_loan]

        if not contract_extension:
            out_list = [t for t in out_list if not t.contract_extension]

    if in_list:
        transfer_list.append({"in": in_list})

    if out_list:
        transfer_list.append({"out": out_list})

    for group in transfer_list:
        if group.get("in"):
            click.echo("Transfers in\n")
            transfer_tuples = []
            for transfer in group["in"]:
                ratio = transfer.get_fee_to_value_ratio()
                if ratio != 0:
                    transfer_tuple = ast.literal_eval(str(transfer))
                    transfer_tuple += (ratio,)
                    transfer_tuples.append(transfer_tuple)
            transfer_tuples = sorted(transfer_tuples, key=lambda d: d[-1])
            click.echo("\n".join(map(str, transfer_tuples)))
        elif group.get("out"):
            click.echo("Transfers out\n")
            click.echo("\n".join(map(str, group["out"])))


if __name__ == '__main__':
    cli()
