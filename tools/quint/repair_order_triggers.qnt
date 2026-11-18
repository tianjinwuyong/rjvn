module repair_order_triggers {
  var mesOnline: bool
  var workOrderCreated: bool
  var manualRequested: bool
  var pendingQuantity: int
  var elapsedMinutes: int
  var periodDue: bool

  // These values are published by MES configuration; the Agent cannot edit them.
  var useManual: bool
  var useTime: bool
  var useQuantity: bool
  var usePeriod: bool
  var requireAll: bool
  var timeThresholdMinutes: int
  var quantityThreshold: int
  var periodMinutes: int
  var policyVersion: int

  action init = all {
    mesOnline' = true,
    workOrderCreated' = false,
    manualRequested' = false,
    pendingQuantity' = 0,
    elapsedMinutes' = 0,
    periodDue' = false,
    useManual' = true,
    useTime' = true,
    useQuantity' = true,
    usePeriod' = false,
    requireAll' = false,
    timeThresholdMinutes' = 60,
    quantityThreshold' = 10,
    periodMinutes' = 120,
    policyVersion' = 1,
  }

  action pressHumanButton = all {
    workOrderCreated == false,
    manualRequested' = true,
    mesOnline' = mesOnline,
    workOrderCreated' = workOrderCreated,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action recordNg(quantity) = all {
    quantity > 0,
    workOrderCreated == false,
    mesOnline' = mesOnline,
    workOrderCreated' = workOrderCreated,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity + quantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action advanceTime(minutes) = all {
    minutes > 0,
    workOrderCreated == false,
    mesOnline' = mesOnline,
    workOrderCreated' = workOrderCreated,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes + minutes,
    periodDue' = elapsedMinutes + minutes >= periodMinutes,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action goOffline = all {
    mesOnline,
    mesOnline' = false,
    workOrderCreated' = workOrderCreated,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action recoverMes = all {
    mesOnline == false,
    mesOnline' = true,
    workOrderCreated' = workOrderCreated,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action createOrderAny = all {
    mesOnline,
    workOrderCreated == false,
    requireAll == false,
    useManual or useTime or useQuantity or usePeriod,
    (useManual and manualRequested) or
      (useTime and elapsedMinutes >= timeThresholdMinutes) or
      (useQuantity and pendingQuantity >= quantityThreshold) or
      (usePeriod and periodDue),
    mesOnline' = mesOnline,
    workOrderCreated' = true,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action createOrderAll = all {
    mesOnline,
    workOrderCreated == false,
    requireAll,
    useManual or useTime or useQuantity or usePeriod,
    (useManual == false or manualRequested),
    (useTime == false or elapsedMinutes >= timeThresholdMinutes),
    (useQuantity == false or pendingQuantity >= quantityThreshold),
    (usePeriod == false or periodDue),
    mesOnline' = mesOnline,
    workOrderCreated' = true,
    manualRequested' = manualRequested,
    pendingQuantity' = pendingQuantity,
    elapsedMinutes' = elapsedMinutes,
    periodDue' = periodDue,
    useManual' = useManual,
    useTime' = useTime,
    useQuantity' = useQuantity,
    usePeriod' = usePeriod,
    requireAll' = requireAll,
    timeThresholdMinutes' = timeThresholdMinutes,
    quantityThreshold' = quantityThreshold,
    periodMinutes' = periodMinutes,
    policyVersion' = policyVersion,
  }

  action step = {
    any {
      pressHumanButton,
      recordNg(5),
      recordNg(10),
      advanceTime(30),
      advanceTime(60),
      goOffline,
      recoverMes,
      createOrderAny,
      createOrderAll,
    }
  }

  val nonNegativeCounters = pendingQuantity >= 0 and elapsedMinutes >= 0
  val policyIsVersioned = policyVersion > 0
}
