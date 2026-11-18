module route_rules {
  type Station = ICT | FCT | DEPANEL | AGING | PACKING | PCBA_SHELL_BINDING | OUTER_BOX_BINDING | PALLET_BINDING | REPAIR

  var mesOnline: bool
  var sourceStation: Station
  var currentStation: Station
  var repairDestination: Station
  var routeRevision: int
  var routePublished: bool

  action init = all {
    mesOnline' = true,
    sourceStation' = ICT,
    currentStation' = ICT,
    repairDestination' = REPAIR,
    routeRevision' = 1,
    routePublished' = true,
  }

  action chooseSource(target) = all {
    currentStation == sourceStation,
    target != REPAIR,
    mesOnline' = mesOnline,
    sourceStation' = target,
    currentStation' = target,
    repairDestination' = repairDestination,
    routeRevision' = routeRevision,
    routePublished' = routePublished,
  }

  // MES publishes the rule; an Agent only consumes it.
  action publishRepairRule(target, revision) = all {
    mesOnline,
    target == REPAIR,
    revision > 0,
    mesOnline' = mesOnline,
    sourceStation' = sourceStation,
    currentStation' = currentStation,
    repairDestination' = target,
    routeRevision' = revision,
    routePublished' = true,
  }

  // The path is generated from the published rule, not selected by the Agent.
  action generateRepairPath = all {
    mesOnline,
    routePublished,
    currentStation == sourceStation,
    sourceStation != REPAIR,
    currentStation' = repairDestination,
    mesOnline' = mesOnline,
    sourceStation' = sourceStation,
    repairDestination' = repairDestination,
    routeRevision' = routeRevision,
    routePublished' = routePublished,
  }

  action generateReturnPath = all {
    mesOnline,
    routePublished,
    currentStation == repairDestination,
    currentStation' = sourceStation,
    mesOnline' = mesOnline,
    sourceStation' = sourceStation,
    repairDestination' = repairDestination,
    routeRevision' = routeRevision,
    routePublished' = routePublished,
  }

  action goOffline = all {
    mesOnline,
    mesOnline' = false,
    sourceStation' = sourceStation,
    currentStation' = currentStation,
    repairDestination' = repairDestination,
    routeRevision' = routeRevision,
    routePublished' = routePublished,
  }

  action recoverMes = all {
    mesOnline == false,
    mesOnline' = true,
    sourceStation' = sourceStation,
    currentStation' = currentStation,
    repairDestination' = repairDestination,
    routeRevision' = routeRevision,
    routePublished' = routePublished,
  }

  action step = {
    any {
      chooseSource(ICT),
      chooseSource(FCT),
      chooseSource(DEPANEL),
      chooseSource(AGING),
      chooseSource(PACKING),
      chooseSource(PCBA_SHELL_BINDING),
      chooseSource(OUTER_BOX_BINDING),
      chooseSource(PALLET_BINDING),
      publishRepairRule(REPAIR, 1),
      publishRepairRule(REPAIR, 2),
      generateRepairPath,
      generateReturnPath,
      goOffline,
      recoverMes,
    }
  }

  val publishedRuleHasRevision = routePublished == false or routeRevision > 0
  val routeNeverLeavesRepairToUnknown = currentStation == repairDestination or currentStation == sourceStation
  val allInvariants = publishedRuleHasRevision and routeNeverLeavesRepairToUnknown
}
