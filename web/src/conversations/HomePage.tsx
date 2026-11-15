import { Link } from 'react-router-dom';
import { MessageSquarePlus, Upload } from 'lucide-react';
import { Button } from '../components/ui';

export function HomePage() {
  return (
    <section className="home-page" aria-labelledby="home-title">
      <h1 id="home-title">A clearer view of your documents.</h1>
      <p className="home-description">
        Ask questions, explore the details, and check answers against the source.
      </p>
      <div className="home-actions">
        <Button asChild>
          <Link to="/new-chat">
            <MessageSquarePlus aria-hidden="true" />
            New chat
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/upload">
            <Upload aria-hidden="true" />
            Upload
          </Link>
        </Button>
      </div>
    </section>
  );
}
