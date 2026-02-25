import os
from typing import List, Union

import httpx
import pytest
from _pytest.reports import TestReport
from cachetools.func import lru_cache
from playwright.sync_api import sync_playwright
from pytest import Config, FixtureRequest, Function, Session, fixture, hookimpl

import config
from apps.apis.cashdesk.api.bo2_api_client import CoreBo2APIClient
from apps.apis.cashdesk.api.cashdesk_api_client import CashDeskAPIClient
from apps.apis.casino_integration.digitain.digitain_api import DigitainAPI
from apps.apis.casino_integration.endorphina.endorphina_api import EndorphinaApi
from apps.apis.casino_integration.fazi.fazi_api import FaziAPI
from apps.apis.crm_api_client import CRMClient
from apps.apis.fintech.http_client_card_engine import HTTPClientCardEngine
from apps.apis.fintech.http_client_crypto_engine import HTTPClientCryptoEngine
from apps.apis.fintech.http_client_fintech import HTTPClientFintech
from apps.apis.mtools_api_client import MToolsAPIClient, MToolsAPIClientOldApi
from apps.apis.player_api import PlayerAPI
from apps.apis.team.team_api_client import TeamApiClient
from apps.apis.team.token_manager import generate_token
from apps.logger_ import get_logger
from apps.scripts.add_allure_id_to_report import add_allure_id_to_markers
from apps.scripts.import_run_to_jira import get_results_by_issue_key, get_results_by_test
from apps.utilities.dict import SharedDict
from apps.utilities.finalizer import Finalizable
from apps.utilities.generated_values import get_random_int, get_random_string
from apps.utilities.http_client_bo import HTTPClientBO
from apps.utilities.infrastructure.grafana.grafana_client import GrafanaClient
from apps.utilities.loggers.rp_logger import get_rp_logger
from apps.utilities.loggers.rp_playwright_api_logger import ApiFilter, ApiLogger, LogLevel
from apps.utilities.pytest_customs.plugins import (
    RP_ENDPOINT,
    RP_FAILED_URLS,
    RP_PROJECT,
    add_options,
    add_rp_defect_type_interface,
    configure_rp,
    is_connection_failed,
    modify_mark_expression_according_to_cabinet,
    modify_mark_expression_according_to_env,
    modify_mark_expression_according_to_license,
    normalize_allure_ids,
    publish_report_on_s3,
    remove_allure_ids_option_if_empty,
    safe_getattr,
    save_rp_launch_id,
    write_ids_for_coverage_report,
)
from apps.utilities.report_portal_helper import step
from test_api.affiliates.constants import (
    AFF_CREDENTIALS,
    CABINET_CREDENTIALS,
    PASSWORD_AT_USER,
    WEBMASTER_AUTO_TEST_LOGIN,
    WEBMASTER_AUTO_TEST_PASSWORD,
)
from test_api.affiliates.http_client_affiliates import HTTPClientAffiliates
from test_api.affiliates.http_client_partners import HTTPClientPartners
from test_api.crm.utilities.constants import CRM_ENV
from test_api.mt.constants import ENVS_CREDENTIALS
from test_api.riddick_partners.constants import (
    ADMIN_LOGIN_DJANGO_ADMIN,
    ADMIN_PASSWORD_DEV,
    ADMIN_PASSWORD_PREPROD,
    RIDDICK_CABINET_CREDENTIALS,
    RIDDICK_CREDENTIALS,
)
from test_api.riddick_partners.http_client_django_admin import HTTPClientDjangoAdmin
from test_api.riddick_partners.http_client_riddick_partners import HTTPClientRiddickPartners
from test_api.riddick_partners.http_client_riddick_partners_cabinet import (
    HTTPClientRiddickPartnersCabinet,
)
from test_api.team.utilities.paths import get_schema_path
from test_ui.affiliates.admin_panel.constants import WEBMASTER_LOGIN

LOGGER = get_logger()
pytest_plugins = ["apps.utilities.pytest_customs.rp_phase_plugin"]
PIPELINE_RUN = bool(os.environ.get("CI_JOB_ID"))
IS_PRODUCTION_RUN = os.getenv("PRODUCTION_RUN") == "true"
GEN_PLAYER_PARAMS_LIST = ["licence", "env", "geo", "admin_login", "admin_pass"]

PLAYER_API: Union[PlayerAPI, None] = None
API_NEW_CLIENT: Union[PlayerAPI, None] = None
ENDORPHINA_API: Union[EndorphinaApi, None] = None
DIGITAIN_API: Union[DigitainAPI, None] = None
FAZI_API: Union[FaziAPI, None] = None
AFFILIATES_API: Union[HTTPClientAffiliates, None] = None
BO: Union[HTTPClientBO, None] = None
AFFILIATES_PARTNERS: Union[HTTPClientPartners, None] = None
CASHDESK: Union[CashDeskAPIClient, None] = None
CORE_BO2: Union[CoreBo2APIClient, None] = None
RIDDICK_PARTNERS_API: Union[HTTPClientRiddickPartners, None] = None
RIDDICK_PARTNERS_CABINET_API: Union[HTTPClientRiddickPartnersCabinet, None] = None
CRM: Union[CRMClient, None] = None
M_TOOL: Union[MToolsAPIClient, None] = None
M_TOOL_OLD: Union[MToolsAPIClientOldApi, None] = None
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()
RIDDICK_PARTNERS_DJANGO_ADMIN: Union[HTTPClientDjangoAdmin, None] = None


def pytest_addoption(parser):
    group = parser.getgroup("api-logging")
    group.addoption(
        "--api-log-level",
        action="store",
        default="ERROR",
        choices=["DEBUG", "INFO", "ERROR"],
        help="API logging level for Playwright network capture.",
    )
    group.addoption(
        "--api-url-substring",
        action="store",
        default=None,
        help="Substring filter for API URLs.",
    )
    group.addoption(
        "--api-url-regex",
        action="store",
        default=None,
        help="Regex filter for API URLs.",
    )
    group.addoption(
        "--api-methods",
        action="store",
        default=None,
        help="Comma-separated HTTP methods to capture (e.g. GET,POST).",
    )
    group.addoption(
        "--api-min-status",
        action="store",
        type=int,
        default=None,
        help="Minimum HTTP status code to capture.",
    )
    group.addoption(
        "--api-max-status",
        action="store",
        type=int,
        default=None,
        help="Maximum HTTP status code to capture.",
    )
    add_options(parser)


def pytest_configure(config: Config):
    configure_rp(config)
    remove_allure_ids_option_if_empty(config)
    add_rp_defect_type_interface(config)
    modify_mark_expression_according_to_license(config)
    modify_mark_expression_according_to_cabinet(config)
    modify_mark_expression_according_to_env(config)


def pytest_sessionfinish(session: Session, exitstatus):
    save_rp_launch_id(session.config)
    is_default_mode = safe_getattr(session, "config.option.rp_mode") != "DEBUG"
    if is_default_mode and (RP_FAILED_URLS or is_connection_failed()):
        RP_FAILED_URLS["rp_endpoint"] = RP_ENDPOINT
        RP_FAILED_URLS["project"] = RP_PROJECT
        LOGGER.warning("[RP] Failed requests: %s", RP_FAILED_URLS)
        rp_launch = safe_getattr(session, "config.option.rp_launch", "Framework")
        publish_report_on_s3(launch_name=rp_launch)


def pytest_collection_modifyitems(session, config: Config, items: List[Function]):
    normalize_allure_ids(config, items)

    if config.getoption("--collect-only"):
        write_ids_for_coverage_report(items)
        return

    add_allure_id_to_markers(items)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    outcome = yield
    report: TestReport = outcome.get_result()

    if report.when == "setup":
        item.is_a_rerun = hasattr(item, "is_a_rerun")
    if report.when == "call":
        if getattr(item, "is_a_rerun", False) and report.passed:
            item.session.config.add_defect("flaky", item.nodeid)
    # setting teardown outcome to passed if previous phases are passed.
    if report.when == "teardown":
        if getattr(item, "test_passed", False):
            if not report.passed:
                item.session.config.add_defect("teardown", item.nodeid)
            report.outcome = "passed"
    else:
        item.test_passed = report.passed

    if report.when == "call":
        api_logger = item._request.getfixturevalue("api_logger_fixture")
        if api_logger:
            plain_text = str(api_logger)
            logger = get_rp_logger()
            logger.propagate = False
            logger.info(
                "API calls log",
                attachment={
                    "name": "api_log.txt",
                    "data": plain_text.encode("utf-8"),
                    "mime": "text/plain",
                },
            )
            api_logger.entries.clear()


@hookimpl()
def pytest_report_teststatus(report: TestReport, config):
    if report.when == "call" and report.passed and config.defects.get(report.nodeid) == "flaky":
        return "flaky", "L", "FLAKY"


def pytest_json_runtest_metadata(item, call):
    """Persist only clean allure IDs into json-report metadata."""
    ids = []

    for m in item.own_markers:
        # 1) @allure.id("KEY-123")
        if m.name == "allure_id" and m.args:
            ids.extend(str(x) for x in m.args if x)

        # 2) @allure_labels(..., tr_ids=("KEY-1","KEY-2")) -> mark.allure_label(label_type="as_id", ...)
        elif m.name == "allure_label" and m.kwargs.get("label_type") == "as_id":
            if m.args:
                ids.extend(str(x) for x in m.args if x)
            for v in (m.kwargs.get("ids_by_licence") or {}).values():
                if isinstance(v, (list, tuple, set)):
                    ids.extend(str(x) for x in v if x)
                elif v:
                    ids.append(str(v))

    clean = set()
    for raw in ids:
        s = str(raw).strip().upper()
        if s.startswith("PARAMETERSET(") or "MARK(" in s:
            continue
        clean.add(s)

    return {"allure_ids": tuple(sorted(clean))}


@fixture()
def results_by_issue_key(request):
    return get_results_by_issue_key(get_results_by_test(path=None))


@fixture(scope="session")
def cli_params(pytestconfig):
    config = {
        param: pytestconfig.getoption(param)
        for param in (
            "env",
            "licence",
            "geo",
            "admin_login",
            "admin_pass",
            "device_type",
            "com_hub_cabinet",
        )
    }

    device_type = config.get("device_type")
    if device_type == "mobile":
        config["device"] = "Pixel 5"
    elif device_type == "desktop":
        config["viewport"] = {"width": 1280, "height": 720}

    return config


@fixture(scope="session")
def set_player_data_per_worker(request: FixtureRequest):
    def wrapper(data_for_workers: list | tuple | str):
        worker_id = request.getfixturevalue("worker_id")
        if worker_id != "master":
            worker_index = int(worker_id.replace("gw", ""))
            if isinstance(data_for_workers, str):
                data = os.getenv(data_for_workers)
                if data:
                    data_for_workers = data.strip().split("|")
                else:
                    return
            try:
                data_for_worker = data_for_workers[worker_index]
                request.config.__setattr__("worker_data", data_for_worker)
            except IndexError or KeyError as e:
                raise e

    yield wrapper


@fixture(scope="session", autouse=True)
def auto_worker_data_setup(set_player_data_per_worker):
    set_player_data_per_worker("PYTEST_WORKERS_DATA")


@fixture(scope="module")
def getoption_licence(request):
    return request.config.getoption("--licence")


@fixture(scope="module")
def getoption_env(request):
    return request.config.getoption("--env")


@fixture(scope="module")
def getoption_geo(request):
    return request.config.getoption("--geo")


@fixture(scope="session")
def spw():
    with sync_playwright() as playwright:
        yield playwright


@fixture(scope="session")
def configure_gen_player(cli_params):
    def wrapper(front_api_configuration=None, bo_api_configuration=None):
        return PlayerAPI(
            licence=cli_params["licence"],
            env=cli_params["env"],
            front_api_configuration=front_api_configuration,
            bo_api_configuration=bo_api_configuration,
            geo=cli_params.get("geo"),
            admin_login=cli_params["admin_login"],
            admin_pass=cli_params["admin_pass"],
        )

    yield wrapper


@fixture()
def gen_player(cli_params):
    global PLAYER_API
    player_params = {k: v for k, v in cli_params.items() if k in GEN_PLAYER_PARAMS_LIST}
    PLAYER_API = PlayerAPI(**player_params)
    yield PLAYER_API


@fixture()
def gen_players(cli_params):
    @step
    def _generate_players(quantity=2, **kwargs):
        player_params = {k: v for k, v in cli_params.items() if k in GEN_PLAYER_PARAMS_LIST}
        return [PlayerAPI(**player_params)(**kwargs) for _ in range(quantity)]

    return _generate_players


@fixture()
def new_player(gen_player):
    yield gen_player(profile_save=False)


@fixture()
def new_verified_player(gen_player):
    yield gen_player("v")


@fixture()
def new_player_with_filled_profile(gen_player):
    yield gen_player(profile_save=True)


@fixture()
def new_player_with_money(gen_player):
    yield gen_player(10_000, profile_save=False)


@fixture()
def non_verified_player_with_money(new_player):
    new_player.bo_api.make_deposit(new_player._id, deposit=10_000)
    yield new_player


@fixture()
def new_player_with_money_and_pincoins(gen_player):
    yield gen_player((200, 200), profile_save=False)


@fixture(scope="function")
def player_with_freespins(gen_player):
    gen_player("v").add_freespins()
    yield gen_player


@fixture(scope="function")
def player_with_bonus(new_player):
    new_player.bo_api.add_bonuses(new_player._id, bonus=10, project="sport")
    yield new_player


@fixture()
def new_player_with_freebet(gen_player, cli_params):
    player = gen_player("v")

    player.bo_api.add_freebet(player._id, freebet=player.bespoke.default_bet_amount)
    assert player.wait_for_player_freebets(), "Freebet was not given."
    yield player


@fixture()
def gen_player_specifying_licences(cli_params):
    global PLAYER_API
    PlayerAPI(
        licence=cli_params["licence"],
        bo_licence=cli_params.get("bo_licence"),
        endorphina_licence=cli_params.get("endorphina_licence"),
        three_oaks_licence=cli_params.get("three_oaks_licence"),
    )
    yield PLAYER_API


@fixture()
def endorphina_api(cli_params):
    global ENDORPHINA_API
    ENDORPHINA_API = ENDORPHINA_API or EndorphinaApi(licence=cli_params["licence"].lower())
    yield ENDORPHINA_API


@fixture(scope="session")
def digitain_api(cli_params):
    global DIGITAIN_API
    DIGITAIN_API = DIGITAIN_API or DigitainAPI(
        licence=cli_params["licence"].lower(), env=cli_params["env"].lower()
    )
    yield DIGITAIN_API


@fixture(scope="session")
def fazi_api(cli_params):
    global FAZI_API
    FAZI_API = FAZI_API or FaziAPI(licence=cli_params["licence"].lower())
    yield FAZI_API


@fixture(scope="session")
def bo(spw, cli_params):
    global BO
    if not BO:
        env = cli_params["env"].lower()
        prod_env = env in ("prod", "preprod")
        BO = HTTPClientBO(
            app_licence=cli_params["licence"].lower(),
            env=env,
            login=config.ADMIN_LOGIN if prod_env else None,
            password=config.ADMIN_PASSWORD if prod_env else None,
        )
    return BO


@lru_cache()
def get_affiliate_client(login, password, pass_code, env):
    return HTTPClientAffiliates(login=login, password=password, pass_code=pass_code, env=env)


@fixture(scope="session")
def affiliates(cli_params):
    login, password, pass_code = AFF_CREDENTIALS[ENVIRONMENT]
    AFFILIATES_API = get_affiliate_client(login, password, pass_code, env=ENVIRONMENT)
    yield AFFILIATES_API


@fixture(scope="function")
def affiliates_user():
    def wrapper(admin_panel_login, admin_panel_password=PASSWORD_AT_USER, pass_code=None):
        global AFFILIATES_API
        if AFFILIATES_API is None or AFFILIATES_API.login != admin_panel_login:
            AFFILIATES_API = HTTPClientAffiliates(
                login=admin_panel_login,
                password=admin_panel_password,
                pass_code=pass_code,
                env=ENVIRONMENT,
            )
            return AFFILIATES_API
        else:
            return AFFILIATES_API

    yield wrapper


@fixture(scope="session")
def shared_data(request):
    root = request.config._tmp_path_factory.getbasetemp().parent
    filepath = root / "shared"

    return SharedDict(filepath)


@fixture(scope="session")
def affiliates_shared_session(cli_params, shared_data):
    login, password, pass_code = AFF_CREDENTIALS[ENVIRONMENT]

    with shared_data.lock:
        if data := shared_data.get("affiliates"):
            return HTTPClientAffiliates(
                login=login,
                password=password,
                pass_code=pass_code,
                env=ENVIRONMENT,
                token=data["token"],
                cookie=data["cookies"],
            )
        affiliates = HTTPClientAffiliates(
            login=login, password=password, pass_code=pass_code, env=ENVIRONMENT
        )
        shared_data["affiliates"] = {"token": affiliates._token, "cookies": affiliates._cookie}
        return affiliates


@fixture(scope="function")
def create_employee(affiliates):
    login = f"automation_test{get_random_string(length=8)}"
    affiliates.create_employee(login)
    yield login


@fixture(scope="session")
def webmaster_cabinet():
    login, password = CABINET_CREDENTIALS[ENVIRONMENT]
    global AFFILIATES_PARTNERS
    if AFFILIATES_PARTNERS is None or AFFILIATES_PARTNERS.login != login:
        AFFILIATES_PARTNERS = HTTPClientPartners(login=login, password=password, env=ENVIRONMENT)
    yield AFFILIATES_PARTNERS


@fixture(scope="function")
def webmaster_cabinet_user():
    def wrapper(
        webmaster_login=WEBMASTER_AUTO_TEST_LOGIN,
        webmaster_password=WEBMASTER_AUTO_TEST_PASSWORD,
    ):
        global AFFILIATES_PARTNERS
        if AFFILIATES_PARTNERS is None or AFFILIATES_PARTNERS.login != webmaster_login:
            AFFILIATES_PARTNERS = HTTPClientPartners(
                login=webmaster_login, password=webmaster_password, env=ENVIRONMENT
            )
            return AFFILIATES_PARTNERS
        else:
            return AFFILIATES_PARTNERS

    yield wrapper


@fixture(scope="session", autouse=True)
def destroy_affiliates_partners_client():
    yield
    Finalizable.clean_up()
    global AFFILIATES_PARTNERS
    if AFFILIATES_PARTNERS:
        AFFILIATES_PARTNERS.close()


@fixture(scope="function")
def register_webmaster(webmaster_cabinet):
    def wrapper(webmaster_login=WEBMASTER_LOGIN):
        test_email = f"{webmaster_login}{get_random_int(length=8)}.com"
        webmaster_cabinet.register_webmaster(test_email)
        return test_email

    yield wrapper


@fixture(scope="function")
def register_and_activate_webmaster(register_webmaster, affiliates):
    def wrapper(webmaster_login=WEBMASTER_LOGIN):
        test_email = register_webmaster(webmaster_login=webmaster_login)
        test_id = affiliates.get_webmaster_registration_entity_by_email(
            email=test_email,
            entities=affiliates.get_users_registration().get("data"),
        ).get("id")
        affiliates.approve_webmaster_registration(email=test_email, test_id=test_id, status=1)
        affiliates.approve_webmaster_registration(email=test_email, test_id=test_id, status=4)
        return test_email

    yield wrapper


@fixture(scope="session")
def httpx_client():
    yield httpx.Client(timeout=httpx.Timeout(60.0, read=None))


@fixture(scope="session")
def cashdesk(request):
    global CASHDESK
    option_env = request.config.getoption("--env")
    option_license = request.config.getoption("--licence")
    CASHDESK = CASHDESK or CashDeskAPIClient(option_env, option_license)
    yield CASHDESK
    Finalizable.clean_up()
    if CASHDESK:
        CASHDESK.close()


@fixture(scope="session")
def core_bo2(request):
    global CORE_BO2
    option_env = request.config.getoption("--env")
    option_license = request.config.getoption("--licence")
    CORE_BO2 = CORE_BO2 or CoreBo2APIClient(option_env, option_license)
    yield CORE_BO2
    Finalizable.clean_up()
    if CORE_BO2:
        CORE_BO2.close()


@fixture(scope="session", autouse=True)
def project_based_on_license_(cli_params):
    projects_for_license = {
        "ua": [{"project": "casino"}],
        "kz": [{"project": "sport"}],
        "com": [{"project": "casino"}, {"project": "sport"}],
    }
    return projects_for_license.get(cli_params.get("licence").lower())


@fixture(scope="session")
def fintech_api():
    return HTTPClientFintech(
        login=os.environ.get("FINTECH_LOGIN"),
        password=os.environ.get("FINTECH_PASSWORD"),
        account_secret=os.environ.get("FINTECH_ACCOUNT_SECRET"),
    )()


@fixture(scope="session")
def crypto_engine_api():
    return HTTPClientCryptoEngine(
        login=os.environ.get("FINTECH_LOGIN"),
        password=os.environ.get("FINTECH_PASSWORD"),
    )()


@fixture(scope="session")
def card_engine_api():
    return HTTPClientCardEngine(
        login=os.environ.get("FINTECH_LOGIN"),
        password=os.environ.get("FINTECH_PASSWORD"),
        account_secret=os.environ.get("FINTECH_ACCOUNT_SECRET"),
    )()


@fixture(scope="session")
def team_api_client():
    env = os.getenv("ENVIRONMENT", "PREPROD").upper()

    def _get_client(token: str):
        return TeamApiClient(env=env, token=token, file_path=get_schema_path("APIPinupTeam.yaml"))

    return _get_client


@fixture(scope="session")
def admin_team_api_client(team_api_client):
    admin_token = generate_token("admin")
    return team_api_client(admin_token)


@fixture(scope="session")
def riddick_partners():
    login, password = RIDDICK_CREDENTIALS[ENVIRONMENT]
    RIDDICK_PARTNERS_API = HTTPClientRiddickPartners(
        login=login, password=password, env=ENVIRONMENT
    )
    yield RIDDICK_PARTNERS_API


@fixture(scope="session")
def riddick_partners_cabinet():
    login, password = RIDDICK_CABINET_CREDENTIALS[ENVIRONMENT]
    RIDDICK_PARTNERS_CABINET_API = HTTPClientRiddickPartnersCabinet(
        login=login, password=password, env=ENVIRONMENT
    )
    yield RIDDICK_PARTNERS_CABINET_API


@fixture(scope="session")
def riddick_partners_django_admin():
    credentials = {
        "dev": (ADMIN_LOGIN_DJANGO_ADMIN, ADMIN_PASSWORD_DEV),
        "preprod": (ADMIN_LOGIN_DJANGO_ADMIN, ADMIN_PASSWORD_PREPROD),
    }
    login, password = credentials[ENVIRONMENT]
    RIDDICK_PARTNERS_DJANGO_ADMIN = HTTPClientDjangoAdmin(
        login=login, password=password, env=ENVIRONMENT
    )
    yield RIDDICK_PARTNERS_DJANGO_ADMIN


@fixture()
def lf(request):
    return request.getfixturevalue(request.param)


@fixture(scope="session")
def crm(request):
    global CRM
    CRM = CRM or CRMClient(CRM_ENV)()
    yield CRM


@fixture(scope="session")
def mt_client(cli_params):
    global M_TOOL
    if M_TOOL is None:
        current_license = os.getenv("LICENCE", cli_params["licence"]).lower()
        current_env = os.getenv("ENVIRONMENT", cli_params["env"]).lower()
        current_env_creds = ENVS_CREDENTIALS[current_env][current_license]
        M_TOOL = MToolsAPIClient(
            login=current_env_creds["login"],
            password=current_env_creds["password"],
            _license=current_license,
            env=current_env,
        )
    yield M_TOOL
    if Finalizable.to_be_cleaned():
        Finalizable.clean_up()
    M_TOOL.close()


@fixture(scope="session")
def mt_client_old_api(cli_params):
    global M_TOOL_OLD
    if M_TOOL_OLD is None:
        current_license = os.getenv("LICENCE", cli_params["licence"]).lower()
        current_env = os.getenv("ENVIRONMENT", cli_params["env"]).lower()
        current_env_creds = ENVS_CREDENTIALS[current_env][current_license]
        M_TOOL_OLD = MToolsAPIClientOldApi(
            login=current_env_creds["login"],
            password=current_env_creds["password"],
            _license=current_license,
            env=current_env,
        )
    yield M_TOOL_OLD()
    if Finalizable.to_be_cleaned():
        Finalizable.clean_up()
    M_TOOL_OLD.close()


@fixture(scope="session")
def mirror_master_client():
    from apps.apis.mirror_master.mirror_master_client import MirrorMasterClient

    mirror_master_client = MirrorMasterClient()
    mirror_master_client.start_stubs()
    yield mirror_master_client


@fixture(scope="session")
def bo_google_oauth_client(cli_params):
    from apps.apis.bo_google_oauth.bo_google_oauth_client import BOGoogleOAuthClient

    return BOGoogleOAuthClient(
        env=cli_params["env"].lower(),
        licence=cli_params["licence"].lower(),
    )


@fixture(scope="session")
def grafana_client(cli_params):
    client = GrafanaClient(
        base_url=os.environ.get("GRAFANA_URL", "https://grafana.time2go.tech"),
        api_token=os.environ.get("GRAFANA_TOKEN"),
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def api_logger_fixture(request) -> ApiLogger:
    log_level = LogLevel(request.config.getoption("--api-log-level"))

    methods_raw = request.config.getoption("--api-methods")
    methods = (
        [m.strip().upper() for m in methods_raw.split(",") if m.strip()] if methods_raw else None
    )

    api_filter = ApiFilter.from_config(
        url_substring=request.config.getoption("--api-url-substring"),
        url_regex=request.config.getoption("--api-url-regex"),
        methods=methods,
        min_status=request.config.getoption("--api-min-status"),
        max_status=request.config.getoption("--api-max-status"),
    )

    return ApiLogger(log_level=log_level, api_filter=api_filter)
