"""
WizNote API server.
"""

import json
import platform
import random
import time
import locale
from typing import Dict
from urllib.parse import urlparse, urljoin, urlencode

import requests

from wizclientpy.utils.urltools import appendSrc
from wizclientpy.sync.wizrequest import exec_request
from wizclientpy.sync.user_info import UserInfo, KbInfo, KbValueVersions
from wizclientpy.sync.token import WizToken
from wizclientpy.utils.classtools import MetaSingleton
from wizclientpy.utils.urltools import buildCommandUrl
from wizclientpy.constants import WIZKM_WEBAPI_VERSION
from wizclientpy.errors import ServerXmlRpcError

WIZNOTE_API_ENTRY = (
    "{server}"  # address of WizNote server
    "?p={product}"  # product, use wiz
    "&l={locale}"  # locale, zh-cn|zh-tw|en-us
    "&v={version}"  # version number
    "&c={command}"  # command, see command list below
    "&random={ramdom}"  # ramdom number
    "&cn={computer_name}"  # computer name, optional
    "&plat={platform}"  # platform, ios|android|web|wp7|x86|x64|linux|macosx
    "&debug={debug}"  # debug, true|false, optional
)

WIZNOTE_API_ARG_PRODUCT = "wiz"

if platform.system() == "Windows":
    WIZNOTE_API_ARG_PLATFORM = "windows"
elif platform.system() == "Darwin":
    WIZNOTE_API_ARG_PLATFORM = "macosx"
elif platform.system() == "Linux":
    WIZNOTE_API_ARG_PLATFORM = "linux"

# API commands
WIZNOTE_API_COMMAND_AS_SERVER = "as"
WIZNOTE_API_COMMAND_SYNC_HTTP = "sync_http"
WIZNOTE_API_COMMAND_SYNC_HTTPS = "sync_https"
WIZNOTE_API_COMMAND_MESSAGE_SERVER = "message_server"
WIZNOTE_API_COMMAND_MESSAGE_VERSION = "message_version"
WIZNOTE_API_COMMAND_AVATAR = "avatar"
WIZNOTE_API_COMMAND_UPLOAD_AVATAR = "upload_avatar"
WIZNOTE_API_COMMAND_USER_INFO = "user_info"
WIZNOTE_API_COMMAND_VIEW_GROUP = "view_group"
WIZNOTE_API_COMMAND_FEEDBACK = "feedback"
WIZNOTE_API_COMMAND_SUPPORT = "support"
WIZNOTE_API_COMMAND_COMMENT = "comment"
WIZNOTE_API_COMMAND_COMMENT_COUNT = "comment_count2"
WIZNOTE_API_COMMAND_CHANGELOG = "changelog"
WIZNOTE_API_COMMAND_UPGRADE = "updatev2"
WIZNOTE_API_COMMAND_MAIL_SHARE = "mail_share2"

WIZNOTE_API_SERVER = "https://api.wiz.cn/"
WIZNOTE_ACOUNT_SERVER = "https://as.wiz.cn/"


class ServerApi:
    """Base class of api object."""
    __server: str

    def __init__(self, strServer: str):
        base_url = urlparse(strServer)
        if base_url.scheme is '':
            base_url = base_url._replace(scheme="https")
        self.__server = base_url.geturl()

    def server(self):
        return self.__server

    def build_url(self, cmd_url: str, token: str = None) -> str:
        """Build full url with a command url."""
        # Construct url
        url = urlparse(cmd_url)
        if url.netloc is '':
            url = urlparse(
                urljoin(self.__server, url.geturl()))
        # Append common parameters
        queries = {
            'clientType': 'macos',
            'clientVersion': None,
            'apiVersion': WIZKM_WEBAPI_VERSION
        }
        if token is not None:
            queries['token'] = token
        url = url._replace(query=urlencode(queries))
        return url.geturl()


class AccountsServerApi(ServerApi):
    """AccountsServerApi is used to manage account related information."""
    __isLogin: bool
    __autoLogout: bool
    __valueVersions: Dict
    __userInfo: UserInfo

    def __init__(self, server: str = WIZNOTE_ACOUNT_SERVER):
        self.__isLogin = False
        self.__autoLogout = False
        self.__valueVersions = {}
        super().__init__(server)

    def login(self, user_name: str, password: str):
        """Login to server and get access token."""
        if self.__isLogin:
            return True
        url = buildCommandUrl(self.__server, "/as/user/login")
        result = exec_request("POST", url, body={
            "userId": user_name,
            "password": password
        })
        # Update user information
        self.__userInfo = UserInfo(result)
        self.__isLogin = True
        return result

    def logout(self) -> bool:
        """Logout the current token."""
        url = buildCommandUrl(
            self.__server, "/as/user/logout", self.__userInfo.strToken)
        result = exec_request("GET", url, token=self.__userInfo.strToken)
        return result

    def keep_alive(self):
        """Extended expiration time of token by 15 min."""
        if self.__isLogin:
            url = buildCommandUrl(
                self.__server, "/as/user/keep", self.__userInfo.strToken)
            result = exec_request("GET", url, token=self.__userInfo.strToken)
            return result
        else:
            raise ServerXmlRpcError("Can not keep alive without login.")

    def fetch_token(self, user_id, password):
        """Get a token by user identity."""
        url = buildCommandUrl(self.__server, "/as/user/token")
        result = exec_request("POST", url, {
            "userId": user_id,
            "password": password
        })
        return result

    def fetch_user_info(self):
        """Get user information from server by token."""
        url = buildCommandUrl(
            self.__server, "/as/user/keep", self.__userInfo.strToken)
        result = exec_request("GET", url, token=self.__userInfo.strToken)
        return result

    def user_info(self) -> UserInfo:
        """Access to user information object."""
        return self.__userInfo

    def set_user_info(self, userInfo: UserInfo):
        """Set new user info."""
        self.__isLogin = True
        self.__userInfo = userInfo

    def fetch_value_versions(self):
        nCountPerPage = 100
        nNextVersion = 0
        url = buildCommandUrl(
            self.__server, "/as/user/kv/versions", self.__userInfo.strToken)
        result = exec_request(
            "GET", url, token=self.__userInfo.strToken, body={
                'version': nNextVersion,
                'count': nCountPerPage,
                'pageSize': nCountPerPage
            }
        )
        kbValVerCollection = []
        for obj in result:
            kbValVerCollection.append(KbValueVersions(obj))
        return kbValVerCollection

    def init_all_value_versions(self):
        versions = self.fetch_value_versions()
        for version in versions:
            self.__valueVersions[version.strKbGUID] = version


class KnowledgeBaseServerApi(ServerApi):
    """WizKMDatabaseServer is used to manage knowledge database."""
    __kbGuid: str
    __token: WizToken

    def __init__(self, server: str, kb_guid: str):
        super().__init__(server)
        self.__kbGuid = kb_guid        

    def download_document(self, doc_guid: str):
        params = {
            "downloadInfo": True,
            "downloadData": True
        }
        url = buildCommandUrl(
            self.__server, f"/ks/note/download/{self.__kbGuid}/{doc_guid}")
        result = exec_request("GET", url, params=params)
        return result
