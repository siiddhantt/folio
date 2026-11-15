import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui';

export function BackButton() {
  const navigate = useNavigate();
  function goBack() {
    // BrowserRouter's index survives reloads and starts at zero for a direct visit.
    if (window.history.state?.idx > 0) navigate(-1);
    else navigate('/', { replace: true });
    document.getElementById('main')?.focus({ preventScroll: true });
  }
  return (
    <Button
      variant="ghost"
      size="icon"
      className="page-back"
      aria-label="Go back"
      title="Go back"
      onClick={goBack}
    >
      <ArrowLeft aria-hidden="true" />
    </Button>
  );
}
