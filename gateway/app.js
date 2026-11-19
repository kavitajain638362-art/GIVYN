import express from 'express'
import gateway from './proxy.js'

const app = express()
app.disable('x-powered-by')
app.use(gateway)

export default app
