import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const outFile = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'mocks', 'report-catalog.json')

const HUMAN = ['json', 'markdown', 'pdf_ready', 'csv', 'campaign_summary']
const BANNER = 'SYNTHETIC FIXTURE. Values in this report are copied from labeled synthetic inputs.'

function jsonText(value) {
  return `${JSON.stringify(value, null, 2)}\n`
}

function part(filename, contentType, body) {
  return { filename, content_type: contentType, body }
}

function documentJson(reportId, kind, scope, packageId, title, sections) {
  return {
    schema_version: '1.0.0',
    report_id: reportId,
    kind,
    scope,
    package_id: packageId,
    synthetic: true,
    title,
    banner: BANNER,
    upstream_input_schema: 'clerk.provisional_upstream.v0',
    sections,
  }
}

function section(sectionId, title, entries) {
  return {
    section_id: sectionId,
    title,
    empty: entries.length === 0,
    entries,
  }
}

function entry(entryId, factClass, epistemic, fields) {
  return {
    entry_id: entryId,
    fact_class: factClass,
    epistemic,
    confirmed: factClass === 'confirmed_observation',
    fields: Object.entries(fields).map(([name, value]) => ({ name, value: String(value) })),
  }
}

const callSections = [
  section('displayed_caller_metadata', 'Displayed caller metadata', [
    entry('syn-call-001', 'reported_caller_metadata', 'raw_observation', {
      displayed_caller_number: '+1-202-555-0143',
      displayed_caller_name: 'CARD SERVICES',
      displayed_callee_number: '+1-555-0100',
    }),
  ]),
  section('transcript_excerpts', 'Transcript excerpts', [
    entry('syn-ex-001', 'raw_observation', 'raw_observation', {
      speaker: 'caller',
      text: 'This is the Visa fraud department. I am agent Marcus.',
    }),
  ]),
  section('spoken_identifiers', 'Spoken identifiers', [
    entry('syn-spk-001', 'spoken_identifier', 'raw_observation', {
      kind: 'organization',
      value: 'Visa',
    }),
  ]),
  section('structured_observations', 'Structured observations', [
    entry('syn-obs-confirmed', 'confirmed_observation', 'raw_observation', {
      text: 'Caller asked the target to install a remote access program.',
    }),
    entry('syn-obs-derived', 'derived_interpretation', 'derived_interpretation', {
      text: 'The remote-access request is the extraction step of this script.',
    }),
  ]),
  section('campaign_association', 'Campaign association', [
    entry('syn-campaign-001', 'derived_association', 'campaign_attribution', {
      campaign_id: 'syn-campaign-001',
      associated: 'true',
      label: 'Visa fraud desk',
    }),
  ]),
]

const campaignSections = [
  section('call_identity', 'Call identity', [
    entry('syn-call-001', 'raw_observation', 'raw_observation', { call_id: 'syn-call-001', session_id: 'syn-session-001' }),
    entry('syn-call-002', 'raw_observation', 'raw_observation', { call_id: 'syn-call-002', session_id: 'syn-session-002' }),
  ]),
  section('displayed_caller_metadata', 'Displayed caller metadata', [
    entry('syn-call-001-meta', 'reported_caller_metadata', 'raw_observation', {
      call_id: 'syn-call-001',
      displayed_caller_number: '+1-202-555-0143',
      displayed_caller_name: 'CARD SERVICES',
    }),
    entry('syn-call-002-meta', 'reported_caller_metadata', 'raw_observation', {
      call_id: 'syn-call-002',
      displayed_caller_number: '+1-202-555-0177',
      displayed_caller_name: 'CARD SERVICES',
    }),
  ]),
  section('spoken_identifiers', 'Spoken identifiers', [
    entry('syn-spk-001', 'spoken_identifier', 'raw_observation', { value: 'Visa', call_id: 'syn-call-001' }),
    entry('syn-spk-002', 'spoken_identifier', 'raw_observation', { value: '1-800-555-0199', call_id: 'syn-call-002' }),
  ]),
  section('structured_observations', 'Structured observations', [
    entry('syn-obs-confirmed', 'confirmed_observation', 'raw_observation', {
      text: 'Both calls name CARD SERVICES and a callback of 1-800-555-0199.',
    }),
    entry('syn-obs-derived', 'derived_interpretation', 'derived_interpretation', {
      text: 'Shared callback and opener are the script overlap supplied with the package.',
    }),
  ]),
  section('association_reasons', 'Association reasons', [
    entry('syn-reason-001', 'derived_association', 'campaign_attribution', {
      campaign_id: 'syn-campaign-001',
      reason: 'Shared spoken callback 1-800-555-0199.',
    }),
  ]),
]

const incidentSections = [
  section('incident_record', 'Incident record', [
    entry('syn-incident-001', 'derived_interpretation', 'derived_interpretation', {
      summary: 'Displayed caller number +1-202-555-0143 is not the SIP From user +1-415-555-0138.',
    }),
  ]),
  section('displayed_caller_metadata', 'Displayed caller metadata', [
    entry('syn-call-001', 'reported_caller_metadata', 'raw_observation', {
      displayed_caller_number: '+1-202-555-0143',
      sip_from_user: '+1-415-555-0138',
    }),
  ]),
  section('transcript_excerpts', 'Transcript excerpts', [
    entry('syn-ex-001', 'raw_observation', 'raw_observation', {
      text: 'This is the Visa fraud department. I am agent Marcus.',
    }),
  ]),
  section('spoken_identifiers', 'Spoken identifiers', [
    entry('syn-spk-001', 'spoken_identifier', 'raw_observation', { value: 'Marcus', kind: 'person_name' }),
  ]),
  section('structured_observations', 'Structured observations', [
    entry('syn-obs-confirmed', 'confirmed_observation', 'raw_observation', {
      text: 'SIP From user and the displayed caller number differ on this leg.',
    }),
  ]),
  section('campaign_association', 'Campaign association', []),
]

function markdown(title, reportId, packageId, body) {
  return `# ${title}

> ${BANNER}

Package ID: ${packageId}
Report ID: ${reportId}
Synthetic: true

${body}`
}

function html(title, reportId) {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>${title}</title></head>
<body>
<p>${BANNER}</p>
<h1>${title}</h1>
<p>Report ID: ${reportId}</p>
<p>Mock PDF-ready projection. The dashboard does not run CLERK's A4 renderer.</p>
</body>
</html>
`
}

function csvCalls(rows) {
  const header = 'call_id,displayed_caller_number,displayed_caller_name,duration_seconds'
  return `${header}\n${rows.join('\n')}\n`
}

function csvObservations(rows) {
  return `entry_id,fact_class,text\n${rows.join('\n')}\n`
}

function summary(packageId, associated, extra) {
  return {
    schema_version: '1.0.0',
    package_id: packageId,
    synthetic: true,
    associated,
    campaign_id: associated ? 'syn-campaign-001' : null,
    fact_class: associated ? 'derived_association' : null,
    epistemic: associated ? 'campaign_attribution' : null,
    label: associated ? 'Visa fraud desk' : null,
    member_call_ids: associated ? extra.members : [],
    packaged_call_ids: associated ? extra.members : [],
    confidence_level: associated ? 'high' : null,
    confidence_score: associated ? 0.86 : null,
    confidence_basis: associated ? 'Confidence supplied with the synthetic campaign record.' : null,
    reason_codes: associated ? extra.reasons : [],
  }
}

function humanRenders(reportId, packageId, kind, title, doc, markdownBody, callRows, observationRows, members) {
  return [
    {
      report_id: reportId,
      format: 'json',
      parts: [part(`${reportId}.json`, 'application/json; charset=utf-8', jsonText(doc))],
    },
    {
      report_id: reportId,
      format: 'markdown',
      parts: [part(`${reportId}.md`, 'text/markdown; charset=utf-8', markdown(title, reportId, packageId, markdownBody))],
    },
    {
      report_id: reportId,
      format: 'pdf_ready',
      parts: [part(`${reportId}.html`, 'text/html; charset=utf-8', html(title, reportId))],
    },
    {
      report_id: reportId,
      format: 'csv',
      parts: [
        part('calls.csv', 'text/csv; charset=utf-8', csvCalls(callRows)),
        part('observations.csv', 'text/csv; charset=utf-8', csvObservations(observationRows)),
      ],
    },
    {
      report_id: reportId,
      format: 'campaign_summary',
      parts: [
        part(
          `${reportId}.campaign_summary.json`,
          'application/json; charset=utf-8',
          jsonText(summary(packageId, members.length > 0, { members, reasons: ['shared_callback'] })),
        ),
      ],
    },
  ]
}

const callId = 'syn-pkg-call-001__single_call'
const campaignId = 'syn-pkg-campaign-001__multi_call_campaign'
const incidentId = 'syn-pkg-incident-001__technical_incident'
const exportId = 'syn-export-synthetic-001__machine_readable_json'

const callTitle = 'Single-call evidence report syn-call-001'
const campaignTitle = 'Multi-call campaign evidence report syn-campaign-001'
const incidentTitle = 'Technical incident evidence report syn-incident-001'
const exportTitle = 'Machine-readable export syn-export-synthetic-001'

const exportBody = {
  export_type: 'clerk.evidence_export',
  schema_version: '1.0.0',
  synthetic: true,
  generated_at: '2026-09-25T18:00:00Z',
  package_ids: ['syn-pkg-call-001', 'syn-pkg-campaign-001', 'syn-pkg-incident-001'],
  packages: [
    {
      schema_version: '1.0.0',
      package_id: 'syn-pkg-call-001',
      synthetic: true,
      generator: 'clerk',
      upstream_input_schema: 'clerk.provisional_upstream.v0',
      scope: 'single_call',
      calls: [
        {
          identity: { call_id: 'syn-call-001', session_id: 'syn-session-001' },
          reported_caller_metadata: {
            fact_class: 'reported_caller_metadata',
            epistemic: 'raw_observation',
            displayed_caller_number: '+1-202-555-0143',
            displayed_caller_name: 'CARD SERVICES',
          },
          transcript_excerpts: [
            {
              excerpt_id: 'syn-ex-001',
              fact_class: 'raw_observation',
              epistemic: 'raw_observation',
              text: 'This is the Visa fraud department. I am agent Marcus.',
            },
          ],
          spoken_identifiers: [
            {
              identifier_id: 'syn-spk-001',
              fact_class: 'spoken_identifier',
              epistemic: 'raw_observation',
              value: 'Visa',
            },
          ],
        },
      ],
      observations: [
        {
          observation_id: 'syn-obs-confirmed',
          fact_class: 'confirmed_observation',
          epistemic: 'raw_observation',
          text: 'Caller asked the target to install a remote access program.',
        },
        {
          observation_id: 'syn-obs-derived',
          fact_class: 'derived_interpretation',
          epistemic: 'derived_interpretation',
          text: 'The remote-access request is the extraction step of this script.',
        },
      ],
      campaign_association: {
        fact_class: 'derived_association',
        epistemic: 'campaign_attribution',
        campaign_id: 'syn-campaign-001',
        associated: true,
      },
    },
  ],
}

const catalog = {
  index: [
    {
      report_id: callId,
      package_id: 'syn-pkg-call-001',
      package_ids: ['syn-pkg-call-001'],
      kind: 'single_call',
      title: callTitle,
      synthetic: true,
      available_formats: HUMAN,
    },
    {
      report_id: campaignId,
      package_id: 'syn-pkg-campaign-001',
      package_ids: ['syn-pkg-campaign-001'],
      kind: 'multi_call_campaign',
      title: campaignTitle,
      synthetic: true,
      available_formats: HUMAN,
    },
    {
      report_id: incidentId,
      package_id: 'syn-pkg-incident-001',
      package_ids: ['syn-pkg-incident-001'],
      kind: 'technical_incident',
      title: incidentTitle,
      synthetic: true,
      available_formats: HUMAN,
    },
    {
      report_id: exportId,
      package_id: 'syn-export-synthetic-001',
      package_ids: ['syn-pkg-call-001', 'syn-pkg-campaign-001', 'syn-pkg-incident-001'],
      kind: 'machine_readable_json',
      title: exportTitle,
      synthetic: true,
      available_formats: ['json'],
    },
  ],
  renders: [
    ...humanRenders(
      callId,
      'syn-pkg-call-001',
      'single_call',
      callTitle,
      documentJson(callId, 'single_call', 'single_call', 'syn-pkg-call-001', callTitle, callSections),
      `## Displayed caller metadata

- fact_class: reported_caller_metadata
- displayed_caller_number: +1-202-555-0143
- displayed_caller_name: CARD SERVICES

## Transcript excerpts

- fact_class: raw_observation
- text: This is the Visa fraud department. I am agent Marcus.

## Spoken identifiers

- fact_class: spoken_identifier
- value: Visa

## Structured observations

- fact_class: confirmed_observation
- text: Caller asked the target to install a remote access program.

- fact_class: derived_interpretation
- text: The remote-access request is the extraction step of this script.

## Campaign association

- fact_class: derived_association
- campaign_id: syn-campaign-001
`,
      ['syn-call-001,+1-202-555-0143,CARD SERVICES,187'],
      [
        'syn-obs-confirmed,confirmed_observation,Caller asked the target to install a remote access program.',
        'syn-obs-derived,derived_interpretation,The remote-access request is the extraction step of this script.',
      ],
      ['syn-call-001'],
    ),
    ...humanRenders(
      campaignId,
      'syn-pkg-campaign-001',
      'multi_call_campaign',
      campaignTitle,
      documentJson(campaignId, 'multi_call_campaign', 'campaign', 'syn-pkg-campaign-001', campaignTitle, campaignSections),
      `## Call identity

- syn-call-001
- syn-call-002

## Association reasons

- fact_class: derived_association
- reason: Shared spoken callback 1-800-555-0199.
`,
      [
        'syn-call-001,+1-202-555-0143,CARD SERVICES,187',
        'syn-call-002,+1-202-555-0177,CARD SERVICES,204',
      ],
      ['syn-reason-001,derived_association,Shared spoken callback 1-800-555-0199.'],
      ['syn-call-001', 'syn-call-002'],
    ),
    ...humanRenders(
      incidentId,
      'syn-pkg-incident-001',
      'technical_incident',
      incidentTitle,
      documentJson(incidentId, 'technical_incident', 'technical_incident', 'syn-pkg-incident-001', incidentTitle, incidentSections),
      `## Incident record

- fact_class: derived_interpretation
- summary: Displayed caller number +1-202-555-0143 is not the SIP From user +1-415-555-0138.

## Displayed caller metadata

- fact_class: reported_caller_metadata
- displayed_caller_number: +1-202-555-0143
- sip_from_user: +1-415-555-0138
`,
      ['syn-call-001,+1-202-555-0143,CARD SERVICES,187'],
      ['syn-incident-001,derived_interpretation,Displayed caller number is not the SIP From user.'],
      [],
    ),
    {
      report_id: exportId,
      format: 'json',
      parts: [part(`${exportId}.json`, 'application/json; charset=utf-8', jsonText(exportBody))],
    },
  ],
}

writeFileSync(outFile, jsonText(catalog))
console.log(`Wrote ${catalog.index.length} reports and ${catalog.renders.length} renders to ${outFile}`)
