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

import argparse
import logging
from typing import Literal, Protocol, Sequence

logger = logging.getLogger(__name__)

from critic import api

name = "delrole"
title = "Unassign role(s) from user"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--username", required=True, help="Name of user to unassign roles from"
    )
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        default=[],
        choices=("administrator", "repositories", "developer", "newswriter"),
        help=(
            "Role. One of: administrator, repositories, developer, " "and newswriter."
        ),
    )

    parser.set_defaults(need_session=True)


class Arguments(Protocol):
    username: str
    roles: Sequence[Literal["administrator", "repositories", "developer", "newswriter"]]


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    assigned_roles = []
    for role in arguments.roles:
        if user.hasRole(role):
            assigned_roles.append(role)
        else:
            logger.info("%s: user does not have role '%s'", user.name, role)

    async with api.transaction.start(critic) as transaction:
        modifier = transaction.modifyUser(user)

        for role in assigned_roles:
            await modifier.deleteRole(role)

    for role in assigned_roles:
        logger.info("Assigned role '%s' to user %s [id=%d]", role, user.name, user.id)

    return 0
