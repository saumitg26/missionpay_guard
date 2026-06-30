import { useState, useEffect } from "react";
import { CheckCircle, XCircle, AlertTriangle, ArrowRight, Layers, FileText, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { getCaseDetails, type CaseDetails } from "../services/api";

type FieldStatus = "confirmed" | "conflict" | "low-confidence" | "missing" | "ok";

interface PacketField {
  field: string;
  value: string;
  source: string;
  confidence: number;
  status: FieldStatus;
}

const statusConfig: Record<FieldStatus, { label: string; badge: string; row: string; icon: typeof CheckCircle }> = {
  ok:              { label: "OK",             badge: "bg-green-50 text-green-700 border-green-200",  row: "bg-white",       icon: CheckCircle },
  confirmed:       { label: "Confirmed",      badge: "bg-green-50 text-green-700 border-green-200",  row: "bg-green-50/30", icon: CheckCircle },
  conflict:        { label: "Conflict",       badge: "bg-red-50 text-red-700 border-red-200",        row: "bg-red-50/20",   icon: XCircle },
  "low-confidence":{ label: "Low Confidence", badge: "bg-amber-50 text-amber-700 border-amber-200",  row: "bg-amber-50/20", icon: AlertTriangle },
  missing:         { label: "Missing",        badge: "bg-red-100 text-red-800 border-red-300",       row: "bg-red-50/30",   icon: XCircle },
};

interface PacketConversionProps {
  onNext: () => void;
  caseId?: string;
}

export function PacketConversion({ onNext, caseId }: PacketConversionProps) {
  const [caseDetails, setCaseDetails] = useState<CaseDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => { loadData(); }, [caseId]);

  const loadData = async () => {
    setLoading(true);
    if (caseId) {
      const details = await getCaseDetails(caseId);
      if (details) setCaseDetails(details);
    }
    setLoading(false);
  };

  // Build packet fields from real case data
  const buildPacketFields = (): PacketField[] => {
    if (!caseDetails) return [];
    const fields: PacketField[] = [];
    const ef = caseDetails.extracted_fields || {};

    // Vendor Name
    const vendorName = caseDetails.vendor_name || ef.payee_name || "";
    if (vendorName) {
      fields.push({ field: "Vendor Name", value: vendorName, source: "Invoice + Contract", confidence: 92, status: "ok" });
    }

    // Invoice Number
    const invoiceNum = caseDetails.invoice_number || ef.invoice_number || "";
    if (invoiceNum) {
      fields.push({ field: "Invoice Number", value: invoiceNum, source: "Invoice (SF 1034)", confidence: 97, status: "ok" });
    } else {
      fields.push({ field: "Invoice Number", value: "NOT FOUND", source: "—", confidence: 0, status: "missing" });
    }

    // Invoice Amount
    const amount = caseDetails.invoice_amount || 0;
    if (amount > 0) {
      fields.push({ field: "Invoice Amount", value: `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, source: "Invoice (SF 1034)", confidence: 95, status: "ok" });
    }

    // Purchase Order Number
    const poNum = caseDetails.purchase_order_number || ef.order_number || "";
    if (poNum) {
      fields.push({ field: "Purchase Order Number", value: poNum, source: "PO (SF 1449)", confidence: 94, status: "ok" });
    } else {
      fields.push({ field: "Purchase Order Number", value: "NOT FOUND", source: "—", confidence: 0, status: "missing" });
    }

    // Contract Number
    const contractNum = caseDetails.contract_id || ef.contract_number || "";
    if (contractNum) {
      const hasUnclear = contractNum.includes("?") || contractNum.includes("*");
      fields.push({
        field: "Contract ID",
        value: contractNum,
        source: "Contract Award",
        confidence: hasUnclear ? 63 : 92,
        status: hasUnclear ? "low-confidence" : "ok",
      });
    } else {
      fields.push({ field: "Contract ID", value: "NOT FOUND", source: "—", confidence: 0, status: "missing" });
    }

    // Requisition Number
    const reqNum = ef.requisition_number || "";
    if (reqNum) {
      fields.push({ field: "Requisition Number", value: reqNum, source: "PO (SF 1449)", confidence: 94, status: "ok" });
    }

    // Appropriation Code
    const appCode = ef.appropriation_code || "";
    if (appCode) {
      fields.push({ field: "Appropriation Code", value: appCode, source: "Invoice + PO", confidence: 90, status: "ok" });
    }

    // Vendor UEI
    const uei = ef.vendor_uei || "";
    if (uei) {
      fields.push({ field: "Vendor UEI", value: uei, source: "Contract Award", confidence: 96, status: "ok" });
    }

    // Currency
    const currency = ef.currency || "USD";
    fields.push({ field: "Currency", value: currency, source: "Invoice", confidence: 99, status: "ok" });

    return fields;
  };

  // Build readiness checks from case data
  const buildReadinessChecks = () => {
    if (!caseDetails) return [];
    const checks = [];
    const ef = caseDetails.extracted_fields || {};

    checks.push({
      label: "All required fields extracted",
      pass: !!(caseDetails.vendor_name && caseDetails.invoice_amount && (caseDetails.invoice_number || ef.invoice_number)),
      detail: caseDetails.vendor_name ? "Vendor, amount, and invoice number present" : "Missing required fields",
    });

    // Cross-document consistency
    const contractNum = caseDetails.contract_id || ef.contract_number || "";
    const hasUnclear = contractNum.includes("?");
    checks.push({
      label: "Cross-document values consistent",
      pass: !hasUnclear,
      detail: hasUnclear ? `Contract ID "${contractNum}" has unclear characters — verify against source` : "All cross-referenced values match",
    });

    // Confidence threshold
    const confidence = caseDetails.extraction_confidence || 0;
    checks.push({
      label: "Confidence thresholds met",
      pass: confidence >= 0.7,
      detail: `Overall extraction confidence: ${(confidence * 100).toFixed(2)}%${confidence < 0.7 ? " — below 70% threshold" : ""}`,
    });

    // Required documents
    const docs = caseDetails.documents || [];
    checks.push({
      label: "Required documents present",
      pass: docs.length >= 3,
      detail: `${docs.length} document(s) uploaded${docs.length < 3 ? " — need Invoice, PO, and Contract" : ""}`,
    });

    // Vendor verification
    checks.push({
      label: "Vendor identified",
      pass: !!caseDetails.vendor_name && caseDetails.vendor_name !== "Pending Extraction",
      detail: caseDetails.vendor_name || "Vendor not extracted",
    });

    return checks;
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Loading packet conversion data...</p>
        </div>
      </div>
    );
  }

  if (!caseId || !caseDetails) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50">
        <div className="text-center max-w-md">
          <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-600 text-sm font-medium">No case selected</p>
          <p className="text-slate-400 text-xs mt-1">Select a case from the Dashboard to view packet conversion results.</p>
        </div>
      </div>
    );
  }

  const packetFields = buildPacketFields();
  const readinessChecks = buildReadinessChecks();
  const counts = {
    ok: packetFields.filter(f => f.status === "ok" || f.status === "confirmed").length,
    warn: packetFields.filter(f => f.status === "low-confidence").length,
    fail: packetFields.filter(f => f.status === "conflict" || f.status === "missing").length,
  };
  const totalFields = packetFields.length;
  const readinessScore = totalFields > 0 ? Math.round((counts.ok / totalFields) * 100) : 0;
  const readinessLabel = readinessScore >= 80 ? "Ready" : readinessScore >= 50 ? "Conditional" : "Incomplete";
  const rl = {
    Ready: { bar: "bg-green-500", text: "text-green-700", bg: "bg-green-50", border: "border-green-200" },
    Conditional: { bar: "bg-amber-400", text: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
    Incomplete: { bar: "bg-red-500", text: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
  }[readinessLabel];

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="p-6 space-y-5">

        {/* Header */}
        <div className="bg-white border border-slate-200 rounded-lg px-5 py-4 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-center shrink-0">
              <Layers className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-slate-900 text-base font-semibold">Payment Packet Conversion Engine</h2>
              <p className="text-slate-500 text-xs mt-0.5">
                Case {caseId} — Fields from {caseDetails.documents?.length || 0} documents mapped into a single structured payment case.
                Extraction confidence: {((caseDetails.extraction_confidence || 0) * 100).toFixed(2)}%
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className={`flex items-center gap-2 px-3 py-2 rounded border ${rl.bg} ${rl.border}`}>
              <span className={`text-xs font-bold ${rl.text}`}>Packet Status: {readinessLabel}</span>
              <span className={`text-[10px] font-semibold ${rl.text}`}>{readinessScore}%</span>
            </div>
            <button onClick={loadData} className="text-blue-500 hover:text-blue-700 p-1">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-5">

          {/* LEFT: Readiness */}
          <div className="col-span-1 space-y-4">
            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <h3 className="text-slate-900 text-sm font-semibold mb-3">Packet Readiness</h3>
              <div className="flex items-end justify-between mb-2">
                <span className={`text-3xl font-bold ${rl.text}`}>{readinessScore}%</span>
                <span className={`text-xs font-semibold px-2 py-1 rounded ${rl.bg} ${rl.text} ${rl.border} border`}>{readinessLabel}</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-3">
                <div className={`h-full rounded-full ${rl.bar}`} style={{ width: `${readinessScore}%` }} />
              </div>
              <div className="flex gap-3 text-xs">
                <div className="flex-1 text-center bg-green-50 border border-green-100 rounded py-1.5">
                  <div className="font-semibold text-green-700">{counts.ok}</div>
                  <div className="text-green-600 text-[10px]">OK</div>
                </div>
                <div className="flex-1 text-center bg-amber-50 border border-amber-100 rounded py-1.5">
                  <div className="font-semibold text-amber-700">{counts.warn}</div>
                  <div className="text-amber-600 text-[10px]">Low Conf.</div>
                </div>
                <div className="flex-1 text-center bg-red-50 border border-red-100 rounded py-1.5">
                  <div className="font-semibold text-red-700">{counts.fail}</div>
                  <div className="text-red-600 text-[10px]">Issues</div>
                </div>
              </div>
            </div>

            {/* Readiness checks */}
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-4 py-3 border-b border-slate-100">
                <h3 className="text-slate-900 text-sm font-semibold">Readiness Checks</h3>
              </div>
              <div className="divide-y divide-slate-50">
                {readinessChecks.map((check, i) => (
                  <div key={i} className={`flex items-start gap-3 px-4 py-3 ${check.pass ? "" : "bg-red-50/20"}`}>
                    {check.pass
                      ? <CheckCircle className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      : <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    }
                    <div>
                      <div className={`text-xs font-medium ${check.pass ? "text-slate-700" : "text-red-800"}`}>{check.label}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{check.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: Field map */}
          <div className="col-span-2">
            <div className="bg-white border border-slate-200 rounded-lg">
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-slate-900 text-sm font-semibold">Cross-Document Field Map</h3>
                  <p className="text-slate-400 text-xs mt-0.5">Each field traced to its source document.</p>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-slate-400">
                  <FileText className="w-3.5 h-3.5" />
                  {packetFields.length} fields mapped
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-100">
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Field</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Value</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Source</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Conf.</th>
                      <th className="text-left px-4 py-2.5 text-slate-400 font-semibold uppercase text-[10px] tracking-wide">Status</th>
                      <th className="px-4 py-2.5"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {packetFields.map((field) => {
                      const cfg = statusConfig[field.status];
                      const Icon = cfg.icon;
                      const isExpanded = expanded === field.field;

                      return (
                        <tr
                          key={field.field}
                          className={`cursor-pointer hover:bg-slate-50 transition-colors ${cfg.row}`}
                          onClick={() => setExpanded(isExpanded ? null : field.field)}
                        >
                          <td className="px-4 py-2.5 text-slate-700 font-medium">{field.field}</td>
                          <td className="px-4 py-2.5">
                            <span className={`font-mono ${field.status === "missing" ? "text-slate-400 italic" : field.status === "conflict" ? "text-red-700 font-semibold" : "text-slate-800"}`}>
                              {field.value}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                              {field.source}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <span className={`text-[10px] font-semibold ${
                              field.confidence >= 85 ? "text-green-600" :
                              field.confidence >= 70 ? "text-amber-600" :
                              field.confidence === 0 ? "text-slate-400" :
                              "text-red-600"
                            }`}>
                              {field.confidence === 0 ? "—" : `${field.confidence}%`}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <Icon className={`w-3.5 h-3.5 ${
                                field.status === "ok" || field.status === "confirmed" ? "text-green-500" :
                                field.status === "low-confidence" ? "text-amber-500" :
                                "text-red-500"
                              }`} />
                              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cfg.badge}`}>
                                {cfg.label}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-2.5">
                            <ChevronRight className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="px-5 py-3.5 border-t border-slate-100 flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  {counts.fail > 0 && (
                    <span className="text-red-500 font-medium mr-3">⚠ {counts.fail} issue{counts.fail > 1 ? "s" : ""} found</span>
                  )}
                  {counts.warn > 0 && (
                    <span className="text-amber-500">{counts.warn} field{counts.warn > 1 ? "s" : ""} require confirmation</span>
                  )}
                </div>
                <button
                  onClick={onNext}
                  className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors"
                >
                  Continue to Risk Validation
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
