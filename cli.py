import ast
import click
from collections import defaultdict
from pprint import pprint 

from fotmoblistserv.api import API
from fotmoblistserv.objects import League, Player, Team, Transfer


def format_data_as_strings(data):
    col_widths = [max(len(str(item)) for item in col) for col in zip(*data)]
    formatted_rows = []
    border_line = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+"
    
    # Adding uppercase header
    header = data[0]
    formatted_header = "|" + "|".join(str(item).upper().center(width + 2) for item, width in zip(header, col_widths)) + "|"
    
    formatted_rows.append(border_line)
    formatted_rows.append(formatted_header)
    formatted_rows.append(border_line)
    
    for row in data[1:]:
        formatted_row = "|" + "|".join(" " + str(item).ljust(width) + " " for item, width in zip(row, col_widths)) + "|"
        formatted_rows.append(formatted_row)
        formatted_rows.append(border_line)
    
    return formatted_rows


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
def save_all_totws(league_id, num_apps):
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


    pprint(player_groupings)



@cli.command()
@click.argument("league_id", required=True)
@click.argument("round_id", required=False)
@click.option("-s", "--sort-by", type=click.INT, default=3)
def get_totw(league_id, round_id, sort_by):
    league = League(league_id)

    try:
        if round_id:
            totw = league.get_totw_for_week(week=round_id)
        else:
            totw = league.get_totw_for_week()
    except ValueError as error:
        click.echo(error)
        return
    
    week = totw['players'][0]['roundNumber']
    name = league.get_name()
    country = league.get_country()

    header = f"{country} - {name} TOTW (Week {week})\n"
    banner = "\n" + "=" * len(header) + "\n"

    click.echo(banner)
    click.echo(header)

    tuples = []
    players = [Player(player["participantId"]) for player in totw["players"]]
    players = sorted(players, key=lambda p: (p.get_age(), -p.get_total_senior_appearances()))
    for player in players:
        tuples.append(player.get_player_tuple())

    tuples = [("name", "club", "position", "age", "apps",)] + tuples
    table = "\n".join(map(str, format_data_as_strings(tuples)))
    click.echo(f"{table}\n")


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
    click.echo(f"\n{team.get_name()} - Transfer Activity\n")

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
            tuples = [ast.literal_eval(str(transfer)) for transfer in group["in"]]
            tuples = sorted(tuples, key=lambda t: -t[-1])
            tuples = [("Name", "Date", "Transfer", "TF", "MV", "TF/MV",)] + tuples
            table = "\n".join(map(str, format_data_as_strings(tuples)))
            click.echo(f"IN: \n\n{table}\n")
        elif group.get("out"):
            tuples = [ast.literal_eval(str(transfer)) for transfer in group["out"]]
            tuples = sorted(tuples, key=lambda t: -t[-1])
            tuples = [("Name", "Date", "Transfer", "TF", "MV", "TF/MV",)] + tuples
            table = "\n".join(map(str, format_data_as_strings(tuples)))
            click.echo(f"OUT: \n\n{table}\n")


if __name__ == '__main__':
    cli()
