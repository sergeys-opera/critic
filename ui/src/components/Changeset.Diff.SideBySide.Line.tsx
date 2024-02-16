import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import Line from "./Changeset.Diff.Line"
import ChangesetComment from "./Changeset.Comment"
import {
  kContextLine,
  kDeletedLine,
  kInsertedLine,
  kModifiedLine,
  kReplacedLine,
  kWhitespaceLine,
  DiffLine,
} from "../resources/diffcommon"
import { FileID, ChangesetID } from "../resources/types"
import { SelectionScope } from "../reducers/uiSelectionScope"
import { LineComments } from "../selectors/fileDiff"
import { locationFromSelectionScope } from "../utils/Comment"

const useStyles = makeStyles((theme: Theme) => ({
  changesetDiffSideBySideLine: {
    display: "flex",
    flexDirection: "row",
  },

  marker: {
    minWidth: theme.spacing(1),
  },
  markerOpenIssue: {
    backgroundColor: theme.palette.issue.open,
  },
  markerClosedIssue: {
    backgroundColor: theme.palette.issue.closed,
  },
  markerNote: {
    backgroundColor: theme.palette.note,
  },

  codeLine: {
    whiteSpace: "pre-wrap",
    flexGrow: 1,
    width: "50%",
  },

  oldLineNumber: {
    minWidth: "3rem",
    textAlign: "right",
    flexGrow: 0,
    paddingRight: theme.spacing(1),
  },
  newLineNumber: {
    minWidth: "3rem",
    textAlign: "left",
    flexGrow: 0,
    paddingLeft: theme.spacing(1),
  },

  comments: {
    display: "grid",
    gridTemplateColumns: "3rem 1fr 1fr 3rem",
    gridTemplateAreas: `
      "empty1 old new empty2"
    `,
  },
  comment: {
    margin: theme.spacing(0, 3, 1, 3),
    background: "rgba(0,0,0,5%)",
    borderBottomLeftRadius: 4,
    borderBottomRightRadius: 4,
  },
  commentOld: {
    gridArea: "old",
  },
  commentNew: {
    gridArea: "new",
  },
}))

type OwnProps = {
  className?: string
  changesetID: ChangesetID
  fileID: FileID
  line: DiffLine
  comments: LineComments | null
  selectionScope: SelectionScope | null
  inView: boolean
}

const SideBySideLine: FunctionComponent<OwnProps> = ({
  className,
  changesetID,
  fileID,
  line,
  comments,
  selectionScope,
  inView,
}) => {
  const oldID = `f${fileID}:${line.oldID}`
  const newID = `f${fileID}:${line.newID}`

  const classes = useStyles()

  const {
    selectedIDs = null,
    lastSelectedID = null,
    isRangeSelecting = false,
    isPending = false,
  } = selectionScope || {}

  const oldIsSelected = selectedIDs?.has(oldID) ?? false
  const newIsSelected = selectedIDs?.has(newID) ?? false

  const hasSelection = selectionScope !== null && !isPending

  const { type } = line
  const { oldSide = null, newSide = null } = comments ?? {}
  const oldMarkerClass = clsx(classes.marker, {
    [classes.markerOpenIssue]: oldSide?.hasOpenIssues,
    [classes.markerClosedIssue]: oldSide?.hasClosedIssues,
    [classes.markerNote]:
      oldSide?.hasNotes && !oldSide?.hasOpenIssues && !oldSide?.hasClosedIssues,
  })
  const newMarkerClass = clsx(classes.marker, {
    [classes.markerOpenIssue]: newSide?.hasOpenIssues,
    [classes.markerClosedIssue]: newSide?.hasClosedIssues,
    [classes.markerNote]:
      newSide?.hasNotes && !newSide?.hasOpenIssues && !newSide?.hasClosedIssues,
  })

  let createCommentOld: React.ReactElement | null = null
  let createCommentNew = null
  if (selectionScope && lastSelectedID !== null && !isRangeSelecting) {
    if (lastSelectedID === oldID) {
      createCommentOld = (
        <ChangesetComment
          key="new-comment-old"
          className={clsx(classes.comment, classes.commentOld)}
          location={{
            changesetID,
            ...locationFromSelectionScope(selectionScope),
          }}
        />
      )
    }
    if (lastSelectedID === newID) {
      createCommentNew = (
        <ChangesetComment
          key="new-comment-new"
          className={clsx(classes.comment, classes.commentNew)}
          location={{
            changesetID,
            ...locationFromSelectionScope(selectionScope),
          }}
        />
      )
    }
  }

  return (
    <>
      <div
        className={clsx(
          className,
          classes.changesetDiffSideBySideLine,
          "line",
          {
            context: type === kContextLine,
            deleted: type === kDeletedLine,
            inserted: type === kInsertedLine,
            modified: type === kModifiedLine,
            replaced: type === kReplacedLine,
            whitespace: type === kWhitespaceLine,
          },
        )}
      >
        <span className={classes.oldLineNumber}>
          {type !== kInsertedLine ? line.oldOffset : null}
        </span>
        <span className={oldMarkerClass} />
        <Line
          className={clsx(classes.codeLine, "old")}
          lineID={oldID}
          line={type !== kInsertedLine ? line : null}
          side={type !== kContextLine ? "old" : null}
          isSelected={oldIsSelected}
          hasSelection={hasSelection}
          inView={inView}
        />
        <span className={oldMarkerClass} />
        <span className={newMarkerClass} />
        <Line
          className={clsx(classes.codeLine, "new")}
          lineID={newID}
          line={type !== kDeletedLine ? line : null}
          side={type !== kContextLine ? "new" : null}
          isSelected={newIsSelected}
          hasSelection={hasSelection}
          inView={inView}
        />
        <span className={newMarkerClass} />
        <span className={classes.newLineNumber}>
          {type !== kDeletedLine ? line.newOffset : null}
        </span>
      </div>
      {createCommentOld !== null ||
      oldSide?.comments.length ||
      createCommentNew !== null ||
      newSide?.comments.length ? (
        <div className={classes.comments}>
          {oldSide?.comments.map((comment) => (
            <ChangesetComment
              key={comment.id}
              comment={comment}
              className={clsx(classes.comment, classes.commentOld)}
            />
          ))}
          {createCommentOld}
          {newSide?.comments.map((comment) => (
            <ChangesetComment
              key={comment.id}
              comment={comment}
              className={clsx(classes.comment, classes.commentNew)}
            />
          ))}
          {createCommentNew}
        </div>
      ) : null}
    </>
  )
}

export default Registry.add(
  "Changeset.Diff.SideBySide.Line",
  React.memo(SideBySideLine),
)