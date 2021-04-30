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
from abc import abstractmethod

from typing import (
    Any,
    Awaitable,
    Callable,
    Literal,
    Optional,
    Protocol,
    Collection,
    Sequence,
    Union,
    overload,
)

from critic import api
from critic.gitaccess import SHA1
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="extension version"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid extension version id is used."""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid extension version name is used."""

    pass


class InvalidSHA1(api.InvalidItemError, Error, item_type="sha1"):
    """Raised when an invalid extension version SHA-1 is used."""

    pass


class NoCurrentVersion(Error):
    """Raised when no current version exists."""

    pass


PackageType = Literal["python"]


class ExtensionVersion(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    @abstractmethod
    async def extension(self) -> api.extension.Extension:
        ...

    @property
    @abstractmethod
    def name(self) -> Optional[str]:
        ...

    @property
    @abstractmethod
    def sha1(self) -> SHA1:
        ...

    class Author(Protocol):
        @property
        def name(self) -> str:
            ...

        @property
        def email(self) -> Optional[str]:
            ...

    class Entrypoint(Protocol):
        @property
        def name(self) -> str:
            ...

        @property
        def target(self) -> str:
            ...

    class PythonPackage(Protocol):
        @property
        def package_type(self) -> Literal["python"]:
            ...

        @property
        def entrypoints(self) -> Collection[ExtensionVersion.Entrypoint]:
            ...

        @property
        def dependencies(self) -> Collection[str]:
            ...

        @property
        def data_globs(self) -> Collection[str]:
            ...

    class Role(Protocol):
        @property
        def description(self) -> str:
            ...

    class ExecutesServerSide(Role, Protocol):
        @property
        def entrypoint(self) -> Optional[str]:
            ...

    class Endpoint(ExecutesServerSide, Protocol):
        @property
        def name(self) -> str:
            ...

    class Subscription(ExecutesServerSide, Protocol):
        @property
        def channel(self) -> str:
            ...

        @property
        def reserved(self) -> bool:
            ...

    class UIAddon(Role, Protocol):
        @property
        def name(self) -> str:
            ...

        @property
        def bundle_js(self) -> Optional[str]:
            ...

        @property
        def bundle_css(self) -> Optional[str]:
            ...

    class Manifest(Protocol):
        @property
        def description(self) -> str:
            ...

        @property
        def authors(self) -> Sequence[ExtensionVersion.Author]:
            ...

        @property
        def package(self) -> Union[ExtensionVersion.PythonPackage]:
            ...

        @property
        def endpoints(self) -> Collection[ExtensionVersion.Endpoint]:
            ...

        @property
        def subscriptions(self) -> Collection[ExtensionVersion.Subscription]:
            ...

        @property
        def ui_addons(self) -> Collection[ExtensionVersion.UIAddon]:
            ...

        @property
        def low_level(self) -> Any:
            ...

    @property
    @abstractmethod
    async def manifest(self) -> Manifest:
        ...


@overload
async def fetch(critic: api.critic.Critic, version_id: int, /) -> ExtensionVersion:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    name: str,
) -> ExtensionVersion:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    sha1: SHA1,
) -> ExtensionVersion:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    current: Literal[True],
) -> ExtensionVersion:
    ...


async def fetch(
    critic: api.critic.Critic,
    version_id: Optional[int] = None,
    *,
    extension: Optional[api.extension.Extension] = None,
    name: Optional[str] = None,
    sha1: Optional[SHA1] = None,
    current: bool = False,
) -> ExtensionVersion:
    return await fetchImpl.get()(critic, version_id, extension, name, sha1, current)


async def fetchAll(
    critic: api.critic.Critic, /, *, extension: Optional[api.extension.Extension] = None
) -> Sequence[ExtensionVersion]:
    return await fetchAllImpl.get()(critic, extension)


resource_name = table_name = "extensionversions"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.extension.Extension],
            Optional[str],
            Optional[SHA1],
            bool,
        ],
        Awaitable[ExtensionVersion],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.extension.Extension]],
        Awaitable[Sequence[ExtensionVersion]],
    ]
] = FunctionRef()
