# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable, Literal, Tuple, Optional, Sequence

logger = logging.getLogger()

from critic import api
from critic.api import extensionversion as public
from critic import extensions
from critic.extensions.manifest.error import ManifestError
from .queryhelper import QueryHelper, QueryResult
from critic.extensions.manifest import Manifest
from critic.extensions.manifest.pythonpackage import PythonPackage
from critic.gitaccess import SHA1
from critic.background import extensiontasks
from .apiobject import APIObjectImplWithId


@dataclass
class AuthorImpl:
    __name: str
    __email: Optional[str]

    @property
    def name(self) -> str:
        return self.__name

    @property
    def email(self) -> Optional[str]:
        return self.__email


@dataclass
class EntrypointImpl:
    __name: str
    __target: str

    @property
    def name(self) -> str:
        return self.__name

    @property
    def target(self) -> str:
        return self.__target


@dataclass
class PythonPackageImpl:
    __entrypoints: Sequence[PublicType.Entrypoint]
    __dependencies: Sequence[str]
    __data_globs: Sequence[str]

    @property
    def package_type(self) -> Literal["python"]:
        return "python"

    @property
    def entrypoints(
        self,
    ) -> Sequence[PublicType.Entrypoint]:
        return self.__entrypoints

    @property
    def dependencies(self) -> Sequence[str]:
        return self.__dependencies

    @property
    def data_globs(self) -> Sequence[str]:
        return self.__data_globs


@dataclass
class RoleImpl:
    __description: str

    @property
    def description(self) -> str:
        return self.__description


@dataclass
class ExecutesServerSide(RoleImpl):
    __entrypoint: Optional[str]

    @property
    def entrypoint(self) -> Optional[str]:
        return self.__entrypoint


@dataclass
class EndpointImpl(ExecutesServerSide):
    __name: str

    @property
    def name(self) -> str:
        return self.__name


@dataclass
class UIAddonImpl(RoleImpl):
    __name: str
    __bundle_js: Optional[str]
    __bundle_css: Optional[str]

    @property
    def name(self) -> str:
        return self.__name

    @property
    def bundle_js(self) -> Optional[str]:
        return self.__bundle_js

    @property
    def bundle_css(self) -> Optional[str]:
        return self.__bundle_css


@dataclass
class SubscriptionImpl(ExecutesServerSide):
    __channel: str
    __reserved: bool

    @property
    def channel(self) -> str:
        return self.__channel

    @property
    def reserved(self) -> bool:
        return self.__reserved


@dataclass
class ManifestImpl:
    __description: str
    __authors: Sequence[PublicType.Author]
    __package: PublicType.PythonPackage
    __endpoints: Sequence[PublicType.Endpoint]
    __ui_addons: Sequence[PublicType.UIAddon]
    __subscriptions: Sequence[PublicType.Subscription]
    __low_level: extensions.extension.Manifest

    @property
    def description(self) -> str:
        return self.__description

    @property
    def authors(self) -> Sequence[PublicType.Author]:
        return self.__authors

    @property
    def package(self) -> PublicType.PythonPackage:
        return self.__package

    @property
    def endpoints(self) -> Sequence[PublicType.Endpoint]:
        return self.__endpoints

    @property
    def ui_addons(self) -> Sequence[PublicType.UIAddon]:
        return self.__ui_addons

    @property
    def subscriptions(
        self,
    ) -> Sequence[PublicType.Subscription]:
        return self.__subscriptions

    @property
    def low_level(self) -> extensions.extension.Manifest:
        return self.__low_level


PublicType = public.ExtensionVersion
ArgumentsType = Tuple[int, int, str, SHA1, object]


class ExtensionVersion(PublicType, APIObjectImplWithId, module=public):
    __manifest: Optional[public.ExtensionVersion.Manifest]

    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__extension_id, self.__name, self.__sha1, manifest) = args
        self.__manifest_low_level = Manifest(manifest)
        try:
            self.__manifest_low_level.parse()
        except ManifestError:
            logger.exception("Failed to parse extension manifest!")
        self.__manifest = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def extension(self) -> api.extension.Extension:
        return await api.extension.fetch(self.critic, self.__extension_id)

    @property
    def name(self) -> Optional[str]:
        return self.__name

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    @property
    async def manifest(self) -> public.ExtensionVersion.Manifest:
        if self.__manifest is None:
            critic = self.critic
            authors = [
                AuthorImpl(author.name, author.email)
                for author in self.__manifest_low_level.authors
            ]
            assert isinstance(self.__manifest_low_level.package, PythonPackage)
            package = PythonPackageImpl(
                [
                    EntrypointImpl(name, target)
                    for name, target in self.__manifest_low_level.package.entrypoints.items()
                ],
                self.__manifest_low_level.package.dependencies,
                self.__manifest_low_level.package.data_globs,
            )
            pages = []
            ui_addons = []
            subscriptions = []
            async with api.critic.Query[Tuple[str, str, str]](
                critic,
                """SELECT name, description, entrypoint
                     FROM extensionendpointroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as endpoints_result:
                async for name, description, entrypoint in endpoints_result:
                    pages.append(EndpointImpl(description, entrypoint, name))
            async with api.critic.Query[Tuple[str, str, Optional[str], Optional[str]]](
                critic,
                """SELECT name, description, bundle_js, bundle_css
                     FROM extensionuiaddonroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as uiaddons_result:
                async for name, description, bundle_js, bundle_css in uiaddons_result:
                    ui_addons.append(
                        UIAddonImpl(name, description, bundle_js, bundle_css)
                    )
            async with api.critic.Query[Tuple[str, bool, str, str]](
                critic,
                """SELECT channel, TRUE, description, entrypoint
                     FROM extensionsubscriptionroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as subscriptions_result:
                async for channel, reserved, description, entrypoint in subscriptions_result:
                    subscriptions.append(
                        SubscriptionImpl(description, entrypoint, channel, reserved)
                    )
            self.__manifest = ManifestImpl(
                self.__manifest_low_level.description,
                authors,
                package,
                pages,
                ui_addons,
                subscriptions,
                self.__manifest_low_level,
            )
        return self.__manifest

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "extension", "name", "sha1", "manifest"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    version_id: Optional[int],
    extension: Optional[api.extension.Extension],
    name: Optional[str],
    sha1: Optional[SHA1],
    current: bool,
) -> PublicType:
    if version_id is not None:
        return await ExtensionVersion.ensureOne(
            version_id, queries.idFetcher(critic, ExtensionVersion)
        )

    conditions = []

    assert extension is not None
    conditions.append("extension={extension}")

    error: Optional[Exception]
    distinct_on: Optional[Sequence[str]] = None
    order_by: Optional[Sequence[str]] = None
    if name is not None:
        conditions.append("extension={extension} AND name={name}")
        error = public.InvalidName(value=name)
    elif sha1 is not None:
        conditions.append("extension={extension} AND sha1={sha1}")
        error = public.InvalidSHA1(value=name)
    elif current:
        distinct_on = ["extension"]
        order_by = ["extension, id DESC"]
        error = public.NoCurrentVersion("no current version")

    return ExtensionVersion.storeOne(
        await queries.query(
            critic,
            queries.formatQuery(
                *conditions,
                distinct_on=distinct_on,
                order_by=order_by,
            ),
            version_id=version_id,
            extension=extension,
            name=name,
            sha1=sha1,
        ).makeOne(ExtensionVersion, error)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, extension: Optional[api.extension.Extension]
) -> Sequence[PublicType]:
    conditions = []
    if extension:
        conditions.append("extension={extension}")
    return ExtensionVersion.store(
        await queries.query(critic, *conditions, extension=extension).make(
            ExtensionVersion
        )
    )
