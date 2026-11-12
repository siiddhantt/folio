import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { UploadPage } from '../documents/UploadPage';
import type { Capabilities } from '../types';

export function HomePage({ capabilities }: { capabilities: Capabilities }) {
  return (
    <div className="document-entry">
      <UploadPage capabilities={capabilities} />
      <Link to="/runs" className="existing-documents">
        Previously uploaded documents
        <ArrowRight aria-hidden="true" />
      </Link>
    </div>
  );
}
