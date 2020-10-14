import asyncdispatch
import ../models/value_objects
import ../models/world/world_repository_interface

type WorldUsecase* = ref object
  repository: IWorldRepository

proc newWorldUsecase*():WorldUsecase =
  return WorldUsecase(
    repository: newIWorldRepository()
  )

proc updateNumber*(this:WorldUsecase, i, number:int) {.async.} =
  await this.repository.findWorld(i)
  await this.repository.updateRandomNumber(i, number)
