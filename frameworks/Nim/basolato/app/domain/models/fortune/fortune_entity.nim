import ../value_objects


type Fortune* = ref object
  id*: int
  message*: string

proc newFortune*():Fortune =
  return Fortune()
