import elabapi_python
import pandas as pd
import os
from dotenv import load_dotenv
from elabapi_python.rest import ApiException


class BatchImporter(object):
    """
    Batch importer for team and group memberships in eLabFTW.

    :param verify_ssl: Set to False if you use a self signed certificate. Also suppresses urllib3 warnings.
    :param debug: Set to True if you want to start the APIclient in dubug mode.
    """

    def __init__(self, verify_ssl=True, debug=False) -> None:
        # Load environment variables
        load_dotenv()
        self.API_KEY = os.environ.get("ELAB_API_KEY")
        self.API_HOST_URL = os.environ.get("ELAB_API_HOST_URL")

        # Configure the api client
        configuration = elabapi_python.Configuration()
        configuration.api_key["api_key"] = self.API_KEY
        configuration.api_key_prefix["api_key"] = "Authorization"
        configuration.host = self.API_HOST_URL
        configuration.debug = debug
        configuration.verify_ssl = verify_ssl  # change to true for production, as a production server should have a valid SSL-certificate

        # Create an instance of the API class
        self.api_client = elabapi_python.ApiClient(configuration)

        # Fix issue with Authorization header not being properly set by the generated lib
        self.api_client.set_default_header(
            header_name="Authorization", header_value=self.API_KEY
        )

        # Supress ssl warnings
        if not verify_ssl:
            import urllib3

            urllib3.disable_warnings()

        self.users_to_modify = None

    def read_excel(self, f: str, columnmap: dict = None) -> None:
        """
        Reads the content of an xlsx file

        :param f: filename of the file to read
        :param columnmap: dict of the column titles if different from default
        """
        userlist = pd.read_excel(f, index_col=None, na_values=["NA"])

        # Map the column titles from human readable in the XLSX to machine-readable ones
        if not columnmap:
            columnmap = {
                "Nachname": "lastname",
                "Vorname": "firstname",
                "E-Mail": "email",
                "Team": "team",
                "Gruppe": "teamgroup",
            }

        userlist = userlist.rename(columns=dict(columnmap))

        userlist = userlist.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

        # Convert the userlist into a directory
        self.users_to_modify = userlist.to_dict("records")

    def read_users_from_server(self) -> dict:
        """
        Reads users from API

        :return dict of of users with email as key
        """
        users = elabapi_python.UsersApi(self.api_client).read_users()

        self.users_by_email = {
            user.email: {"id": user.userid, "data": user} for user in users
        }

        return self.users_by_email

    def read_teams_from_server(self) -> dict:
        """
        Reads teams from API

        :return dict of teams with name (str) as key
        """
        teams = elabapi_python.TeamsApi(self.api_client).read_teams()
        self.teams_by_name = {
            team_from_server.name: {"id": team_from_server.id, "data": team_from_server}
            for team_from_server in teams
        }
        return self.teams_by_name

    def read_teamgroups_from_server(self) -> dict:
        """
        Reads teamgroups from API

        :return dict of teams with teamgroups and names (str) as keys
        """
        teamgroups = elabapi_python.TeamgroupsApi(self.api_client)
        self.teamgroups_by_name = {}

        for k, v in self.teams_by_name.items():
            self.teamgroups_by_name[k] = {
                teamgroup.name: teamgroup
                for teamgroup in teamgroups.read_team_teamgroups(v.get("id"))
            }

        return self.teamgroups_by_name

    def find_userid_by_email(self, email: str) -> int:
        """
        Get the user id by email

        :param email: str with email of a user

        :return int
        """
        user = self.users_by_email.get(email)

        if not user:
            return None

        return user.get("id")

    def find_teamid_by_name(self, teamname: str) -> int:
        """
        Get the team id by team name

        :param teamname: str with team name

        :return int
        """
        team = self.teams_by_name.get(teamname)

        if not team:
            return None

        return team.get("id")

    def find_teamgroupid_by_names(self, teamname: str, teamgroupname: str):
        """
        Get the teamgroup id by team name and teamgroup name

        :param teamname: name of the team
        :param teamgroupname: name of the teamgroup within the team

        :return int
        """
        teamgroup = self.teamgroups_by_name.get(teamname).get(teamgroupname)

        if not teamgroup:
            return None

        return teamgroup.id

    def add_user_to_team(self, email:str, team:str) -> object:
        """
        Add a user to a team

        :param email: email of the user
        :param team: name of the team

        :return Updated user
        """
        if not email or not team:
            raise ValueError("Email and Team must to be set")

        user_id = self.find_userid_by_email(email)
        team_id = self.find_teamid_by_name(team)

        if not user_id:
            raise NotFoundException(f"User with email {email} not found on server.\n")

        if not team_id:
            raise NotFoundException(f"Team with name {team} not found on server.\n")

        try:
            # At the moment the api throws an error if you want add an user to a team
            # when the user is already member of that team. This will be adressed in a future update.
            # For more details see https://github.com/elabftw/elabftw/issues/4192#issuecomment-1458222167
            updated = elabapi_python.UsersApi(self.api_client).patch_user(
                user_id, body={"action": "add", "team": team_id}
            )
            print("User ", email, "added to team", team, "with team id", team_id)
        except ApiException as err:
            print(
                "While processing",
                email,
                "with team",
                team,
                "the API raised an",
                err.reason,
            )
            print("Propably the user is already in that team. ")
            updated = None

        return updated

    def add_user_to_teamgroup(self, email: str, team: str, teamgroup: str) -> object:
        """
        Add a user to a teamgroup

        :param email: email of the user
        :param team: name of the team
        :param teamgroup name of the teamgroup

        :return Updated teamgroup
        """
        if not email or not team or not teamgroup:
            raise ValueError("Email, Team and Teamgroup must to be set")

        user_id = self.find_userid_by_email(email)
        team_id = self.find_teamid_by_name(team)
        teamgroup_id = self.find_teamgroupid_by_names(team, teamgroup)

        if not user_id:
            raise NotFoundException(f"User with email {email} not found on server.\n")

        if not team_id:
            raise NotFoundException(
                f"Team with name {team} for user {email} not found on server.\n"
            )

        if not teamgroup_id:
            raise NotFoundException(
                f"Teamgroup {teamgroup} in team {team} for user {email} not found on server.\n"
            )

        groupmembers = [
            user.userid
            for user in self.teamgroups_by_name.get(team).get(teamgroup).users
        ]

        if user_id in groupmembers:
            print(
                "User",
                email,
                "is already in teamgroup",
                teamgroup,
                "- Skipped to next record.",
            )
            return None

        updated = elabapi_python.TeamgroupsApi(self.api_client).patch_teamgroup(
            team_id,
            teamgroup_id,
            body={"how": "add", "userid": user_id},
        )
        print(
            "User ",
            email,
            "added to teamgroup",
            teamgroup,
            "with teamgroup id",
            teamgroup_id,
            "in team",
            team,
        )

        return updated

    def process(self, filename: str) -> None:
        """
        Process the excel file and run the import

        :param filename: name of the excel file that will be imported

        """
        print(" #####", "\n", "\n", "Read data from ", self.API_HOST_URL)
        self.read_users_from_server()
        self.read_teams_from_server()
        self.read_teamgroups_from_server()

        print(" *****", "\n", "\n", "Start processing file ", filename)
        self.read_excel(filename)

        for user in self.users_to_modify:
            print(
                "\n",
                "*****",
                "\n",
                "\n",
                'Now processing user "',
                user["firstname"],
                user["lastname"],
                '" identified by email "',
                user["email"],
                '"',
            )
            try:
                self.add_user_to_team(user["email"], user["team"])
                self.add_user_to_teamgroup(user["email"], user["team"], user["teamgroup"])
            except NotFoundException as e:
                # Log error to console if user not found
                print(str(e))


        print("\n", "Processing completed", "\n", "\n", "#####")

        self.read_users_from_server()
        self.read_teams_from_server()
        self.read_teamgroups_from_server()


class NotFoundException(Exception):
    """
    Custom exception if user, team or teamgroup doesn't exist on the server (or could not be mapped)
    """

    def __init__(self, msg) -> None:
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


if __name__ == "__main__":
    importer = BatchImporter(verify_ssl=False)
    importer.process("userlist.xlsx")
