module repair_loop {
  type Status = NG_CONFIRMED | REPAIR_RECEIVED | RETEST_AUTHORIZED | CLOSED

  var status: Status
  var retestCount: int
  pure val MAX_RETESTS = 2

  action init = all {
    status' = NG_CONFIRMED,
    retestCount' = 0,
  }

  action receiveRepair = all {
    status == NG_CONFIRMED,
    status' = REPAIR_RECEIVED,
    retestCount' = retestCount,
  }

  action authorizeRetest = all {
    status == REPAIR_RECEIVED,
    retestCount < MAX_RETESTS,
    status' = RETEST_AUTHORIZED,
    retestCount' = retestCount + 1,
  }

  action closeRepair = all {
    status == RETEST_AUTHORIZED,
    status' = CLOSED,
    retestCount' = retestCount,
  }

  action step = {
    any {
      receiveRepair,
      authorizeRetest,
      closeRepair,
    }
  }

  val retestLimit = retestCount <= MAX_RETESTS
}
