// Runs independent requests together without letting one failure hide the others (unlike Promise.all, which rejects
// as soon as any of them fails). Each result is either in `values` or its error is in `errors`, under the same name.
export async function loadIndependently<T extends Record<string, () => Promise<unknown>>>(loaders: T): Promise<{
  values: { [K in keyof T]?: Awaited<ReturnType<T[K]>> }
  errors: { [K in keyof T]?: Error }
}> {
  const names = Object.keys(loaders) as (keyof T)[]
  const settled = await Promise.allSettled(names.map(name => loaders[name]()))
  const values: { [K in keyof T]?: Awaited<ReturnType<T[K]>> } = {}
  const errors: { [K in keyof T]?: Error } = {}
  settled.forEach((result, index) => {
    const name = names[index]
    if (result.status === 'fulfilled') values[name] = result.value as Awaited<ReturnType<T[typeof name]>>
    else errors[name] = result.reason instanceof Error ? result.reason : new Error(String(result.reason))
  })
  return { values, errors }
}
