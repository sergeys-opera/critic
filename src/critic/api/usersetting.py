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

from abc import abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Sequence,
    TypeVar,
    Tuple,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="user setting"):
    """Base exception for all errors related to the UserSetting class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid user setting id is used"""

    pass


class NotDefined(Error):
    """Raised when the requested user setting is not defined."""

    def __init__(self, scope: str, name: str) -> None:
        """Constructor"""
        super().__init__("User setting not defined: %s:%s" % (scope, name))
        self.scope = scope
        self.name = name


class InvalidScope(Error):
    """Raied when an invalid scope is used."""

    def __init__(self, scope: str) -> None:
        """Constructor"""
        super().__init__("Invalid scope: %r" % scope)
        self.scope = scope


class InvalidName(Error):
    """Raied when an invalid name is used."""

    def __init__(self, name: str) -> None:
        """Constructor"""
        super().__init__("Invalid name: %r" % name)
        self.name = name


class UserSetting(api.APIObjectWithId):
    """Representation of a user setting"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The setting's unique id"""
        ...

    @property
    @abstractmethod
    async def user(self) -> api.user.User:
        """The user whose setting this is"""
        ...

    @property
    @abstractmethod
    def scope(self) -> str:
        """The setting's scope"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The setting's name"""
        ...

    @property
    @abstractmethod
    def value(self) -> Any:
        """The setting's value

        The value is stored as JSON but returned in parsed form, and can thus
        be a dictionary, list, string, number, boolean or None."""
        ...


@overload
async def fetch(critic: api.critic.Critic, usersetting_id: int, /) -> UserSetting:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, scope: str, name: str) -> UserSetting:
    ...


async def fetch(
    critic: api.critic.Critic,
    usersetting_id: Optional[int] = None,
    *,
    scope: Optional[str] = None,
    name: Optional[str] = None,
) -> UserSetting:
    """Fetch a UserSetting object with the given its id or scope and name

    If 'usersetting_id' is not None, 'scope' and 'name' must be None. If
    'usersetting_id' is None, 'scope' and 'name' must both be non-None.

    Only the effective user's settings can be accessed.

    Exceptions:

      InvalidId: if 'usersetting_id' is used but the id is not
                            valid.
      NotDefined: if 'scope' and 'name' are used but no such
                             setting is defined."""
    return await fetchImpl.get()(critic, usersetting_id, scope, name)


T = TypeVar("T")


async def get(
    critic: api.critic.Critic, /, scope: str, name: str, *, default: T
) -> Tuple[T, bool]:
    try:
        setting = await fetch(critic, scope=scope, name=name)
    except NotDefined:
        return default, False
    else:
        return setting.value, True


async def fetchAll(
    critic: api.critic.Critic, *, scope: Optional[str] = None
) -> Sequence[UserSetting]:
    """Fetch UserSetting objects for all settings

    Only the effective user's settings can be accessed.

    If 'scope' is not None, only settings with a matching scope are
    fetched."""
    return await fetchAllImpl.get()(critic, scope)


resource_name = table_name = "usersettings"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[str],
            Optional[str],
        ],
        Awaitable[UserSetting],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[str],
        ],
        Awaitable[Sequence[UserSetting]],
    ]
] = FunctionRef()