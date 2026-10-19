// Abort together, then wait for UI cleanup so an old finally block cannot
// clear the new answer's loading state or overwrite its message list.
export async function interruptAnswerStreams(primary, captures = [], reason = 'message-edit') {
  const controllers = [...new Set([primary, ...captures].filter(Boolean))]
  for (const controller of controllers) controller.abort(reason)
  await Promise.all(controllers.map(controller => controller.finished))
}
