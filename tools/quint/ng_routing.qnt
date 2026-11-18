module ng_routing {
  type Station = ICT | FCT | DEPANEL | AGING | PACKING | PCBA_SHELL_BINDING | OUTER_BOX_BINDING | PALLET_BINDING | REPAIR
  type Status = GOOD | NG_CONFIRMED | REPAIR_RECEIVED | RETEST_AUTHORIZED | RETURN_PENDING | CLOSED

  pure val MAX_RETESTS = 2

  var station: Station
  var sourceStation: Station
  var status: Status
  var retestCount: int
  var mesOnline: bool

  action init = all {
    station' = ICT,
    sourceStation' = ICT,
    status' = GOOD,
    retestCount' = 0,
    mesOnline' = true,
  }

  action chooseStation(target) = all {
    status == GOOD,
    target != REPAIR,
    station' = target,
    sourceStation' = target,
    status' = status,
    retestCount' = retestCount,
    mesOnline' = mesOnline,
  }

  action confirmNg = all {
    status == GOOD,
    station' = station,
    sourceStation' = station,
    status' = NG_CONFIRMED,
    retestCount' = retestCount,
    mesOnline' = mesOnline,
  }

  action routeToRepair = all {
    status == NG_CONFIRMED,
    mesOnline,
    station' = REPAIR,
    sourceStation' = sourceStation,
    status' = REPAIR_RECEIVED,
    retestCount' = retestCount,
    mesOnline' = mesOnline,
  }

  action authorizeRetest = all {
    status == REPAIR_RECEIVED,
    station == REPAIR,
    mesOnline,
    retestCount < MAX_RETESTS,
    station' = REPAIR,
    sourceStation' = sourceStation,
    status' = RETEST_AUTHORIZED,
    retestCount' = retestCount + 1,
    mesOnline' = mesOnline,
  }

  action retestPass = all {
    status == RETEST_AUTHORIZED,
    station == REPAIR,
    station' = sourceStation,
    sourceStation' = sourceStation,
    status' = RETURN_PENDING,
    retestCount' = retestCount,
    mesOnline' = mesOnline,
  }

  action closeAtSource = all {
    status == RETURN_PENDING,
    station == sourceStation,
    mesOnline,
    station' = station,
    sourceStation' = sourceStation,
    status' = CLOSED,
    retestCount' = retestCount,
    mesOnline' = mesOnline,
  }

  action goOffline = all {
    mesOnline,
    station' = station,
    sourceStation' = sourceStation,
    status' = status,
    retestCount' = retestCount,
    mesOnline' = false,
  }

  action recoverMes = all {
    mesOnline == false,
    station' = station,
    sourceStation' = sourceStation,
    status' = status,
    retestCount' = retestCount,
    mesOnline' = true,
  }

  action step = {
    any {
      chooseStation(ICT),
      chooseStation(FCT),
      chooseStation(DEPANEL),
      chooseStation(AGING),
      chooseStation(PACKING),
      chooseStation(PCBA_SHELL_BINDING),
      chooseStation(OUTER_BOX_BINDING),
      chooseStation(PALLET_BINDING),
      confirmNg,
      routeToRepair,
      authorizeRetest,
      retestPass,
      closeAtSource,
      goOffline,
      recoverMes,
    }
  }

  val retestLimit = retestCount <= MAX_RETESTS
  val returnMustTargetSource = status != RETURN_PENDING or station == sourceStation
  // MES-online is enforced by the closeAtSource action guard; these are the
  // state invariants that must hold for every reachable state.
  val allInvariants = retestLimit and returnMustTargetSource
}
