import React from "react"

import Registry from "."
import TrackedBranches from "./Repository.Settings.TrackedBranches"
import Policies from "./Repository.Settings.Policies"
import { AppendPrefix } from "../utils/PrefixContext"
import VerticalMenu from "./VerticalMenu"

const Sections: React.FunctionComponent = () => (
  <AppendPrefix append="settings">
    <VerticalMenu parameterName="section">
      <TrackedBranches />
      <Policies />
    </VerticalMenu>
  </AppendPrefix>
)

export default Registry.add("Repository.Settings", Sections)
