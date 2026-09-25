import reportCatalogJson from './report-catalog.json'
import { parseReportCatalog } from './parseReports'

export const reportCatalog = parseReportCatalog(reportCatalogJson)
