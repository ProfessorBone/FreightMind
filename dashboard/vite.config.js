import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'node:fs'
import path from 'node:path'
import { execFile } from 'node:child_process'

const WORKSPACE_DIR = '/Users/clarencedowns/.openclaw/agents/jack-crawford/workspace'
const PYTHON_BIN = 'python3'

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = ''
    req.on('data', (chunk) => {
      data += chunk
    })
    req.on('end', () => resolve(data))
    req.on('error', reject)
  })
}

function runMemoryCommand(command, payload) {
  const script = `
import json
import sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(WORKSPACE_DIR)})
from tril.will_graham_memory import WillGrahamMemoryStore
from tril.hazmat_memory import HazmatCaseStore
from tril.bol_extract import extract_bol_text
from tril.placard_decision import evaluate_placard
from tril.hazmat_ocr import extract_text_from_document
from tril.hazmat_sources import HazmatSourceIndex
from tril.hazmat_retrieval import context1_retrieval_bundle

payload = json.loads(sys.argv[2])
command = sys.argv[1]

if command in ('create_trip', 'append_event'):
    store = WillGrahamMemoryStore(Path(${JSON.stringify(path.join(WORKSPACE_DIR, 'will-memory'))}))
    if command == 'create_trip':
        result = store.create_or_update_trip(
            date=payload.get('date') or None,
            trip_number=payload['trip_number'],
            stops=payload.get('stops') or [],
            raw_message=payload.get('raw_message'),
        )
    else:
        result = store.append_shorthand_update(
            date=payload.get('date') or None,
            trip_number=payload['trip_number'],
            raw_message=payload['raw_message'],
        )
elif command == 'create_hazmat_case':
    store = HazmatCaseStore(Path(${JSON.stringify(path.join(WORKSPACE_DIR, 'hazmat-memory'))}))
    source_text = payload.get('source_text') or ''
    file_reference = payload.get('file_reference')
    if file_reference and not source_text:
        source_text = extract_text_from_document(file_reference)
    case = store.create_case(
        task_summary=payload['task_summary'],
        source_name=payload['source_name'],
        source_text=source_text,
        source_date=payload.get('source_date'),
        file_reference=file_reference,
    )
    extraction = extract_bol_text(source_text)
    decision = evaluate_placard(extraction)
    primary = extraction.get('commodity_lines', [{}])[0] if extraction.get('commodity_lines') else {}
    retrieval = context1_retrieval_bundle(
        case_summary=payload['task_summary'],
        extracted_identifiers={
            'proper_shipping_name': primary.get('proper_shipping_name'),
            'un_na_number': primary.get('un_na_number'),
            'hazard_class_division': primary.get('hazard_class_division'),
            'packing_group': primary.get('packing_group'),
            'quantity': primary.get('quantity'),
        },
        index_path=Path(${JSON.stringify(path.join(WORKSPACE_DIR, 'hazmat-memory', 'hazmat_source_index.json'))}),
    )
    result = store.update_case(case['case_id'], {
        'source_text': source_text,
        'extracted_fields': extraction,
        'retrieval_evidence': retrieval,
        'hazmat_detected': decision['hazmat_detected'],
        'placard_required': decision['placard_required'],
        'indicated_placards': decision['indicated_placards'],
        'regulatory_citations': decision['regulatory_citations'],
        'assumptions': decision['assumptions'],
        'uncertainty': decision['uncertainty'],
        'confidence_level': decision['confidence_level'],
        'recommended_next_action': decision['recommended_next_action'],
    })
elif command == 'build_hazmat_source_index':
    index = HazmatSourceIndex(
        Path(${JSON.stringify(path.join(WORKSPACE_DIR, 'hazmat-corpus-seed'))}),
        Path(${JSON.stringify(path.join(WORKSPACE_DIR, 'hazmat-memory', 'hazmat_source_index.json'))}),
    )
    result = index.build()
else:
    raise SystemExit('unknown command')

print(json.dumps(result))
`

  return new Promise((resolve, reject) => {
    execFile(PYTHON_BIN, ['-c', script, command, JSON.stringify(payload)], { cwd: WORKSPACE_DIR }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr || error.message))
        return
      }
      resolve(stdout ? JSON.parse(stdout) : null)
    })
  })
}

function liveWorkspacePlugin() {
  return {
    name: 'live-workspace',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url === '/api/trips' && req.method === 'POST') {
          try {
            const body = JSON.parse(await readBody(req))
            const result = await runMemoryCommand('create_trip', body)
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: true, result }))
          } catch (error) {
            res.statusCode = 500
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: false, error: error.message }))
          }
          return
        }

        const eventMatch = req.url?.match(/^\/api\/trips\/([^/]+)\/events$/)
        if (eventMatch && req.method === 'POST') {
          try {
            const body = JSON.parse(await readBody(req))
            body.trip_number = decodeURIComponent(eventMatch[1])
            const result = await runMemoryCommand('append_event', body)
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: true, result }))
          } catch (error) {
            res.statusCode = 500
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: false, error: error.message }))
          }
          return
        }

        if (req.url === '/api/hazmat/cases' && req.method === 'POST') {
          try {
            const body = JSON.parse(await readBody(req))
            const result = await runMemoryCommand('create_hazmat_case', body)
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: true, result }))
          } catch (error) {
            res.statusCode = 500
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.end(JSON.stringify({ ok: false, error: error.message }))
          }
          return
        }

        if (!req.url?.startsWith('/data/')) return next()
        const filename = req.url.slice('/data/'.length)
        const filePath = path.join(WORKSPACE_DIR, filename)
        fs.readFile(filePath, 'utf-8', (err, content) => {
          if (err) return next()
          const ext = path.extname(filename).toLowerCase()
          const mime = ext === '.yaml' || ext === '.yml'
            ? 'text/yaml'
            : ext === '.json'
              ? 'application/json'
              : 'text/markdown'
          res.setHeader('Content-Type', `${mime}; charset=utf-8`)
          res.setHeader('Cache-Control', 'no-store')
          res.end(content)
        })
      })
    },
  }
}

export default defineConfig({
  plugins: [liveWorkspacePlugin(), react(), tailwindcss()],
  assetsInclude: ['**/*.yaml', '**/*.md'],
})
