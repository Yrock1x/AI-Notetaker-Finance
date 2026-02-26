import type { Document } from "@/types";
import { formatFileSize } from "@/lib/utils";
import { FileText, File, FileSpreadsheet, Presentation } from "lucide-react";

interface DocumentListProps {
  documents: Document[];
}

const FILE_ICONS: Record<string, typeof FileText> = {
  pdf: FileText,
  docx: File,
  xlsx: FileSpreadsheet,
  pptx: Presentation,
  txt: FileText,
};

export function DocumentList({ documents }: DocumentListProps) {
  return (
    <div className="rounded-lg border bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b text-left text-sm text-muted-foreground">
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Size</th>
            <th className="px-4 py-3 font-medium">Uploaded</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => {
            const Icon = FILE_ICONS[doc.document_type] ?? FileText;
            return (
              <tr
                key={doc.id}
                className="border-b last:border-0 hover:bg-muted/50"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{doc.title}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm uppercase text-muted-foreground">
                  {doc.document_type}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {formatFileSize(doc.file_size)}
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {new Date(doc.created_at).toLocaleDateString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
