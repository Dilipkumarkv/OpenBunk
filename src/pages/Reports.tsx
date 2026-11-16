import { useToast } from '../components/toastContext'
import { collectionBreakdown, dailySales, reportCatalogue } from '../data/sampleData'

export default function Reports() {
  const toast = useToast()

  return (
    <>
      <div className="heading">
        <div>
          <h1>Reports</h1>
          <div className="sub">Operational and financial summaries.</div>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => toast('CSV export prepared in a full build.')}>
            ⇩ Export CSV
          </button>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="cardhead">
            <h3>Daily sales summary</h3>
            <span className="pill blue">Today</span>
          </div>
          <table>
            <tbody>
              {dailySales.map((row) =>
                'total' in row && row.total ? (
                  <tr key={row.product}>
                    <td>
                      <b>{row.product}</b>
                    </td>
                    <td className="right">
                      <b>{row.volume}</b>
                    </td>
                    <td className="right">
                      <b>{row.value}</b>
                    </td>
                  </tr>
                ) : (
                  <tr key={row.product}>
                    <td>{row.product}</td>
                    <td className="right">{row.volume}</td>
                    <td className="right">{row.value}</td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="cardhead">
            <h3>Collection breakdown</h3>
          </div>
          <table>
            <tbody>
              {collectionBreakdown.map((row) => (
                <tr key={row.mode}>
                  <td>{row.mode}</td>
                  <td className="right">{row.amount}</td>
                  <td className="right">
                    <span className={`pill ${row.tone}`}>{row.share}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="cardhead">
          <h3>Available report catalogue</h3>
          <span className="small">Prototype preview</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Report</th>
              <th>Category</th>
              <th>Description</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {reportCatalogue.map((report) => (
              <tr key={report.name}>
                <td>{report.name}</td>
                <td>{report.category}</td>
                <td>{report.description}</td>
                <td>
                  <button className="btn" onClick={() => toast(`${report.name} preview`)}>
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
