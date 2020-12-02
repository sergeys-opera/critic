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

import logging
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api

from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from ..item import Insert
from ..useremail.create import CreateUserEmail


class CreatedUser(CreateAPIObject[api.user.User], api_module=api.user):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        name: str,
        fullname: str,
        email: Optional[str],
        email_status: Optional[api.useremail.Status],
        hashed_password: Optional[str],
        status: api.user.Status,
        external_account: Optional[api.externalaccount.ExternalAccount],
    ) -> api.user.User:
        critic = transaction.critic
        allow_user_registration = api.critic.settings().users.allow_registration
        verify_email_addresses = api.critic.settings().users.verify_email_addresses

        if (
            external_account is not None
            and critic.session_type == "user"
            and critic.actual_user is None
            and critic.external_account == external_account
            and external_account.provider is not None
        ):
            # This is a session where the user has authenticated using an external
            # authentication provider, but no Critic user was connected to the
            # external account.
            configuration = external_account.provider.configuration
            if (
                not configuration["allow_user_registration"]
                and not allow_user_registration
            ):
                raise api.user.Error("user registration not enabled")
            if email_status is None:
                if (
                    not configuration["verify_email_address"]
                    or not verify_email_addresses
                ):
                    email_status = "trusted"
                else:
                    email_status = "unverified"
        elif critic.session_type == "user" and critic.actual_user is None:
            if not allow_user_registration:
                raise api.user.Error("user registration not enabled")
            if email_status is None:
                if not verify_email_addresses:
                    email_status = "trusted"
                else:
                    email_status = "unverified"
        else:
            api.PermissionDenied.raiseUnlessSystem(critic)
            if email_status is None:
                email_status = "trusted"

        user = await CreatedUser(transaction).insert(
            name=name, fullname=fullname, password=hashed_password, status=status
        )

        if email is not None:
            useremail = await CreateUserEmail.make(
                transaction, user, email, email_status
            )

            await transaction.execute(
                Insert("selecteduseremails").values(uid=user, email=useremail)
            )

            await transaction.execute(
                Insert("usergitemails").values(email=email, uid=user)
            )

        return user
