import React, { FunctionComponent } from "react"

import Registry from "."
import CommitList from "./Commit.List"
import Rebase from "./Review.Commits.Rebase"
import { Partition } from "../resources/review"

type Props = {
  className?: string
  index: number
  partition: Partition
}

const ReviewCommitsPartition: FunctionComponent<Props> = ({
  className,
  index,
  partition,
}) => {
  const rebase =
    partition.rebase !== null ? <Rebase rebaseID={partition.rebase} /> : null
  return (
    <>
      <CommitList
        className={className}
        scopeID={`partition${index}`}
        commitIDs={partition.commits}
        withProgress
      />
      {rebase}
    </>
  )
}

export default Registry.add("Review.Commits.Partition", ReviewCommitsPartition)