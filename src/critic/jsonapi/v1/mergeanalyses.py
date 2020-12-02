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
from typing import (
    Awaitable,
    Collection,
    Mapping,
    List,
    Sequence,
    TypedDict,
)

logger = logging.getLogger(__name__)

from .filediffs import Chunk, select_reduce_chunk

from critic import api
from ..exceptions import UsageError
from ..parameters import Parameters
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import sorted_by_id
from ..valuewrapper import ValueWrapper

MacroChunks = Mapping[str, Sequence[Chunk]]
ChangesRelativeParent = TypedDict(
    "ChangesRelativeParent",
    {
        "parent": api.commit.Commit,
        "files": Awaitable[ValueWrapper[Collection[api.file.File]]],
        "macro_chunks": Awaitable[MacroChunks],
    },
)


class MergeAnalyses(
    ResourceClass[api.mergeanalysis.MergeAnalysis], api_module=api.mergeanalysis
):
    contexts = (None, "repositories", "commits")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.mergeanalysis.MergeAnalysis
    ) -> JSONResult:
        await value.ensure(block=False)

        reduce_chunk = select_reduce_chunk(parameters)

        async def macro_chunks(
            changeset: api.mergeanalysis.MergeChangeset,
        ) -> MacroChunks:
            return {
                str(file.id): [reduce_chunk(chunk) for chunk in chunks]
                for file, chunks in (await changeset.getMacroChunks()).items()
            }

        async def changes_relative_parents() -> List[ChangesRelativeParent]:
            return [
                {
                    "parent": changeset.parent,
                    "files": sorted_by_id(changeset.files),
                    "macro_chunks": macro_chunks(changeset),
                }
                for changeset in await value.changes_relative_parents
            ]

        return {
            "merge": value.merge,
            "changes_relative_parents": changes_relative_parents(),
            "conflict_resolutions": value.conflict_resolutions,
        }

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> api.mergeanalysis.MergeAnalysis:
        merge = await parameters.deduce(api.commit.Commit)
        if not merge:
            raise UsageError.missingParameter("commit")
        return await api.mergeanalysis.fetch(merge)
