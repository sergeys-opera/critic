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
from typing import  Protocol

logger = logging.getLogger(__name__)

from critic import api
from critic import auth

name = "disconnect"
title = "Disconnect external account"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--username", required=True, help="Name of Critic user to connect."
    )
    parser.add_argument(
        "--provider", required=True, help=("External authentication provider.")
    )

    parser.set_defaults(need_session=True)


class Arguments(Protocol):
    username: str
    provider: str


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    enabled_providers = auth.Provider.enabled()
    provider = enabled_providers.get(arguments.provider)

    if provider is None:
        logger.error("%s: invalid provider", arguments.provider)
        if enabled_providers:
            logger.info(
                "Valid choices are: %s", ", ".join(sorted(enabled_providers.keys()))
            )
        else:
            logger.info("No providers are enabled.")
        return 1

    try:
        external_account = await api.externalaccount.fetch(
            critic, provider_name=provider.name, user=user
        )
    except api.externalaccount.NotFound:
        logger.error(
            "%s: user is not connected to a %s", user.name, provider.getTitle()
        )
        return 1

    async with api.transaction.start(critic) as transaction:
        await transaction.modifyUser(user).disconnectFrom(external_account)

    logger.info(
        "%s: disconnected from %s %r",
        user.name,
        provider.getTitle(),
        external_account.account_id,
    )

    return 0