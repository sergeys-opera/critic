/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { fetch, withArguments } from "../resources"
import { Channel } from "../utils/WebSocket"
import Changeset from "../resources/changeset"
import { AsyncThunk } from "../state"
import FileDiff from "../resources/filediff"
import { assertNotNull } from "../debug"
import { ChangesetID, FileID, RepositoryID, ReviewID } from "../resources/types"
import { waitForCompletionLevel } from "../utils/Changeset"
import { withData } from "../resources/requestoptions"

export const loadFileDiff = (
  changesetID: ChangesetID,
  fileID: FileID,
): AsyncThunk<FileDiff | null> => async (dispatch, getState) => {
  if (getState().resource.filediffs.has(`${changesetID}:${fileID}`)) return null
  return (await dispatch(loadFileDiffs([fileID], { changesetID })))[0]
}

export const loadFileDiffs = (
  fileIDs: Iterable<FileID>,
  {
    changeset,
    changesetID,
    repositoryID,
    reviewID,
  }: {
    changeset?: Changeset
    changesetID?: ChangesetID
    repositoryID?: RepositoryID
    reviewID?: ReviewID
  },
): AsyncThunk<FileDiff[]> => async (dispatch) => {
  let isComplete = false

  if (changeset) {
    changesetID = changeset.id
    isComplete = changeset.completionLevel.has("full")
  }

  const channel = !isComplete
    ? await dispatch(Channel.subscribe(`changesets/${changesetID}`))
    : null

  const { status, primary } = await dispatch(
    fetch(
      "filediffs",
      withArguments([...fileIDs]),
      withData({
        changeset,
        changesetID,
        reviewID,
        repositoryID,
      }),
    ),
  )

  if (status === "delayed") {
    assertNotNull(channel)

    await waitForCompletionLevel(channel, { changeset })

    return await dispatch(
      loadFileDiffs(fileIDs, { changesetID, repositoryID, reviewID }),
    )
  }

  return primary
}
