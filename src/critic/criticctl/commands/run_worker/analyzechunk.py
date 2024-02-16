# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import difflib
import re
from typing import List, Optional, Sequence, Tuple


re_ignore = re.compile("^\\s*(?:[{}*]|else|do|\\*/)?\\s*$")
re_words = re.compile("([0-9]+|[A-Z][a-z]+|[A-Z]+|[a-z]+|[\\[\\]{}()]|\\s+|.)")
re_ws = re.compile("\\s+")
re_conflict = re.compile("^<<<<<<< .*$|^=======$|^>>>>>>> .*$")


def analyzeChunk(
    deletedLines: Sequence[str], insertedLines: Sequence[str], moved: bool = False
) -> Optional[str]:
    # Pure delete or pure insert, nothing to analyze.
    if not deletedLines or not insertedLines:
        return None

    # Large chunk, analysis would be expensive, so skip it.
    if len(deletedLines) * len(insertedLines) <= 10000 and not moved:
        analysis = analyzeChunk1(deletedLines, insertedLines)
    else:
        deletedLinesNoWS = [re_ws.sub(" ", line.strip()) for line in deletedLines]
        insertedLinesNoWS = [re_ws.sub(" ", line.strip()) for line in insertedLines]

        sm = difflib.SequenceMatcher(None, deletedLinesNoWS, insertedLinesNoWS)
        blocks = sm.get_matching_blocks()

        edits: List[str] = []

        pi = 0
        pj = 0

        for i, j, n in blocks:
            if not n:
                continue

            if i > pi and j > pj:
                edits.append(
                    analyzeChunk1(
                        deletedLines[pi:i], insertedLines[pj:j], offsetA=pi, offsetB=pj
                    )
                )

            edits.append(
                analyzeWhiteSpaceChanges(
                    deletedLines[i : i + n],
                    insertedLines[j : j + n],
                    offsetA=i,
                    offsetB=j,
                    full=moved,
                )
            )

            pi = i + n
            pj = j + n

        if pi < len(deletedLines) and pj < len(insertedLines):
            edits.append(
                analyzeChunk1(
                    deletedLines[pi:], insertedLines[pj:], offsetA=pi, offsetB=pj
                )
            )

        analysis = ";".join(filter(None, edits))

    if analysis:
        return analysis
    else:
        return ""


def analyzeChunk1(
    deletedLines: Sequence[str],
    insertedLines: Sequence[str],
    offsetA: int = 0,
    offsetB: int = 0,
) -> str:
    matches: List[
        Tuple[
            float, int, int, Sequence[str], Sequence[str], difflib.SequenceMatcher[str]
        ]
    ] = []
    equals: List[Tuple[int, int]] = []

    if len(deletedLines) * len(insertedLines) > 10000:
        return ""

    def ratio(
        sm: difflib.SequenceMatcher[str],
        a: Sequence[str],
        b: Sequence[str],
        aLength: int,
        bLength: int,
    ) -> float:
        matching = 0
        for i, _, n in sm.get_matching_blocks():
            matching += sum(map(len, map(str.strip, a[i : i + n])))
        if aLength > 5 and len(sm.get_matching_blocks()) == 2:
            return float(matching) / aLength
        else:
            return 2.0 * matching / (aLength + bLength)

    for deletedIndex, deleted in enumerate(deletedLines):
        deletedStripped = deleted.strip()
        deletedNoWS = re_ws.sub("", deletedStripped)

        # Don't match conflict lines against anything.
        if re_conflict.match(deleted):
            continue

        if not re_ignore.match(deleted):
            deletedWords: Sequence[str] = re_words.findall(deleted)

            for insertedIndex, inserted in enumerate(insertedLines):
                insertedStripped = inserted.strip()
                insertedNoWS = re_ws.sub("", insertedStripped)

                if not re_ignore.match(inserted):
                    insertedWords: Sequence[str] = re_words.findall(inserted)
                    sm = difflib.SequenceMatcher(None, deletedWords, insertedWords)
                    r = ratio(
                        sm,
                        deletedWords,
                        insertedWords,
                        len(deletedNoWS),
                        len(insertedNoWS),
                    )
                    if r > 0.5:
                        matches.append(
                            (
                                r,
                                deletedIndex,
                                insertedIndex,
                                deletedWords,
                                insertedWords,
                                sm,
                            )
                        )
                elif deletedStripped == insertedStripped:
                    equals.append((deletedIndex, insertedIndex))
        else:
            for insertedIndex, inserted in enumerate(insertedLines):
                if deletedStripped == inserted.strip():
                    equals.append((deletedIndex, insertedIndex))

    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)

        final: List[
            Tuple[
                int,
                int,
                Optional[Sequence[str]],
                Optional[Sequence[str]],
                Optional[difflib.SequenceMatcher[str]],
            ]
        ] = []

        while matches:
            (
                r,
                deletedIndex,
                insertedIndex,
                deletedWords,
                insertedWords,
                sm,
            ) = matches.pop(0)
            final.append((deletedIndex, insertedIndex, deletedWords, insertedWords, sm))
            matches = list(
                filter(
                    lambda data: data[1] != deletedIndex
                    and data[2] != insertedIndex
                    and (data[1] < deletedIndex) == (data[2] < insertedIndex),
                    matches,
                )
            )
            equals = list(
                filter(
                    lambda data: (data[0] < deletedIndex) == (data[1] < insertedIndex),
                    equals,
                )
            )

        final.sort()
        equals.sort()
        result = []

        previousDeletedIndex = -1
        previousInsertedIndex = -1

        final.append((len(deletedLines), len(insertedLines), None, None, None))

        for (
            deletedIndex,
            insertedIndex,
            deletedWordsOrNone,
            insertedWordsOrNone,
            smOrNone,
        ) in final:
            while equals and (
                equals[0][0] < deletedIndex or equals[0][1] < insertedIndex
            ):
                di, ii = equals.pop(0)
                if (
                    previousDeletedIndex < di < deletedIndex
                    and previousInsertedIndex < ii < insertedIndex
                ):
                    deletedLine = deletedLines[di]
                    insertedLine = insertedLines[ii]
                    lineDiff = analyzeWhiteSpaceLine(deletedLine, insertedLine)
                    if lineDiff:
                        result.append(
                            "%d=%d:ws,%s" % (di + offsetA, ii + offsetB, lineDiff)
                        )
                    else:
                        result.append("%d=%d" % (di + offsetA, ii + offsetB))
                    previousDeletedIndex = di
                    previousInsertedIndex = ii
                while equals and (di == equals[0][0] or ii == equals[0][1]):
                    equals.pop(0)

            if smOrNone is None:
                break
            sm = smOrNone

            lineDiffItems = []
            deletedLine = deletedLines[deletedIndex]
            insertedLine = insertedLines[insertedIndex]
            if (
                deletedLine != insertedLine
                and deletedLine.strip() == insertedLine.strip()
            ):
                lineDiffItems.append("ws")
                lineDiffItems.append(analyzeWhiteSpaceLine(deletedLine, insertedLine))
            else:
                assert deletedWordsOrNone is not None
                deletedWords = deletedWordsOrNone
                assert insertedWordsOrNone is not None
                insertedWords = insertedWordsOrNone
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "replace":
                        lineDiffItems.append(
                            "r%d-%d=%d-%d"
                            % (
                                offsetInLine(deletedWords, i1),
                                offsetInLine(deletedWords, i2),
                                offsetInLine(insertedWords, j1),
                                offsetInLine(insertedWords, j2),
                            )
                        )
                    elif tag == "delete":
                        lineDiffItems.append(
                            "d%d-%d"
                            % (
                                offsetInLine(deletedWords, i1),
                                offsetInLine(deletedWords, i2),
                            )
                        )
                    elif tag == "insert":
                        lineDiffItems.append(
                            "i%d-%d"
                            % (
                                offsetInLine(insertedWords, j1),
                                offsetInLine(insertedWords, j2),
                            )
                        )
            lineDiff = f"{deletedIndex + offsetA}={insertedIndex + offsetB}"
            if lineDiffItems:
                lineDiff += f":{','.join(lineDiffItems)}"
            result.append(lineDiff)

            previousDeletedIndex = deletedIndex
            previousInsertedIndex = insertedIndex

        return ";".join(result)
    elif deletedLines[-1] == insertedLines[-1]:
        ndeleted = len(deletedLines)
        ninserted = len(insertedLines)
        result = []
        index = 1

        while (
            index <= ndeleted
            and index <= ninserted
            and deletedLines[-index] == insertedLines[-index]
        ):
            result.append(
                "%d=%d" % (ndeleted - index + offsetA, ninserted - index + offsetB)
            )
            index += 1

        return ";".join(reversed(result))
    else:
        return ""


def offsetInLine(words: Sequence[str], offset: int) -> int:
    return sum([len(word) for word in words[0:offset]])


re_ws_words = re.compile("( |\t|\\s+|\\S+)")


def analyzeWhiteSpaceLine(deletedLine: str, insertedLine: str) -> str:
    deletedWords: Sequence[str] = list(filter(None, re_ws_words.findall(deletedLine)))
    insertedWords: Sequence[str] = list(filter(None, re_ws_words.findall(insertedLine)))

    sm = difflib.SequenceMatcher(None, deletedWords, insertedWords)
    lineDiff = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            lineDiff.append(
                "r%d-%d=%d-%d"
                % (
                    offsetInLine(deletedWords, i1),
                    offsetInLine(deletedWords, i2),
                    offsetInLine(insertedWords, j1),
                    offsetInLine(insertedWords, j2),
                )
            )
        elif tag == "delete":
            lineDiff.append(
                "d%d-%d"
                % (offsetInLine(deletedWords, i1), offsetInLine(deletedWords, i2))
            )
        elif tag == "insert":
            lineDiff.append(
                "i%d-%d"
                % (offsetInLine(insertedWords, j1), offsetInLine(insertedWords, j2))
            )

    return ",".join(lineDiff)


def analyzeWhiteSpaceChanges(
    deletedLines: Sequence[str],
    insertedLines: Sequence[str],
    at_eof: bool = False,
    offsetA: int = 0,
    offsetB: int = 0,
    full: bool = False,
) -> str:
    result = []

    for index, (deletedLine, insertedLine) in enumerate(
        zip(deletedLines, insertedLines)
    ):
        if deletedLine != insertedLine:
            result.append(
                "%d=%d:%s"
                % (
                    index + offsetA,
                    index + offsetB,
                    analyzeWhiteSpaceLine(deletedLine, insertedLine),
                )
            )
        elif index == len(deletedLines) - 1 and at_eof:
            result.append("%d=%d:eol" % (index + offsetA, index + offsetB))
        elif full:
            result.append("%d=%d" % (index + offsetA, index + offsetB))

    if not result and (offsetA or offsetB):
        result.append("%d=%d" % (offsetA, offsetB))

    return ";".join(result)