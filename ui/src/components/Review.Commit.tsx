import React, { FunctionComponent } from "react"

import Registry from "."
import NotFound from "./Application.NotFound"
import LoaderBlock from "./Loader.Block"
import ChangesetSingleCommit from "./Changeset.SingleCommit"
import Breadcrumb from "./Breadcrumb"
import { resolveRef } from "../actions/commit"
import {
  useReview,
  useSubscriptionIf,
  useResource,
  useResourceExtra,
} from "../utils"
import { useRouteMatch } from "react-router"

type Params = {
  ref: string
}

const ReviewCommit: FunctionComponent = () => {
  const {
    params: { ref },
  } = useRouteMatch<Params>()
  const commits = useResource("commits")
  const commitRefs = useResourceExtra("commitRefs")
  const review = useReview()
  useSubscriptionIf(typeof review?.repository === "number", resolveRef, [
    ref,
    review?.repository,
  ])
  if (!review) return null
  const commitID = commitRefs.get(`${review.repository}:${ref}`) ?? -1
  if (!(typeof commitID === "number")) return <NotFound />
  const commit = commits.byID.get(commitID)
  if (!commit) return <LoaderBlock />
  return (
    <Breadcrumb category="commit" label={commit.sha1.substring(0, 8)}>
      <ChangesetSingleCommit commit={commit} />
    </Breadcrumb>
  )
}

export default Registry.add("Review.Commit", ReviewCommit)