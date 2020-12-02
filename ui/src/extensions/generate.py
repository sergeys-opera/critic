from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import List, TextIO, TypedDict

EXTENSIONS_DIR = Path(__file__).parent


class ExtensionInfo(TypedDict):
    name: str
    sha1: str


HEADER = """\
/* Generated by ui/src/extensions/generate.py. DO NOT MODIFY! */

import React, { useEffect, useState } from "react"

import { WithCritic } from "../extension"

const Extensions = () => {"""

TEMPLATES = {
    "useState": """\
  const [%(name)s, set%(name)s] = useState<
    React.FunctionComponent<{}>
  >(() => () => null)""",
    "useEffect": """\

  useEffect(() => {
    import(
      /* webpackChunkName: "%(name)s" */ "./%(name)s"
    ).then((module) => set%(name)s(() => module.default))
  })""",
    "render": """\
      <WithCritic extensionKey="%(name)s">
        <EmailDelivery />
      </WithCritic>""",
}

RETURN = """\

  return (
    <>"""

FOOTER = """\
    </>
  )
}

export default Extensions"""


def emit(stream: TextIO, info: ExtensionInfo, name: str) -> None:
    print(TEMPLATES[name] % info, file=stream)


def main() -> int:
    infos: List[ExtensionInfo]

    try:
        with (EXTENSIONS_DIR / "uiaddons.json").open("r") as uiaddons_json:
            infos = json.load(uiaddons_json)["uiaddons"]
    except FileNotFoundError:
        infos = []

    with (EXTENSIONS_DIR / "index.tsx").open("w") as index_tsx:
        print(HEADER, file=index_tsx)

        for info in infos:
            emit(index_tsx, info, "useState")
            emit(index_tsx, info, "useEffect")

        print(RETURN, file=index_tsx)

        for info in infos:
            emit(index_tsx, info, "render")

        print(FOOTER, file=index_tsx)

    return 0


if __name__ == "__main__":
    sys.exit(main())
