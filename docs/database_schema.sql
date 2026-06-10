-- Conceptual PostgreSQL schema for the transition portal.
-- The POC uses SQLAlchemy models to create equivalent tables on startup.

CREATE TYPE user_role AS ENUM ('staff', 'owner', 'cmc', 'admin');
CREATE TYPE transition_status AS ENUM ('not_started', 'training_in_progress', 'first_call_pending', 'in_progress', 'go_live_ready', 'completed', 'blocked');
CREATE TYPE assignment_status AS ENUM ('active', 'inactive');
CREATE TYPE call_type AS ENUM ('first_call', 'follow_up');
CREATE TYPE call_status AS ENUM ('scheduled', 'completed', 'cancelled', 'needs_reschedule');

CREATE TABLE users (
  id uuid PRIMARY KEY,
  email text UNIQUE NOT NULL,
  full_name text NOT NULL,
  role user_role NOT NULL,
  is_admin boolean DEFAULT false,
  is_active boolean DEFAULT true,
  zoom_user_id text,
  microsoft_user_id text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE properties (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  address text NOT NULL,
  old_tool_property_id text,
  new_tool_property_id text,
  transition_status transition_status NOT NULL DEFAULT 'not_started',
  owner_user_id uuid NOT NULL REFERENCES users(id),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE property_staff (
  id uuid PRIMARY KEY,
  property_id uuid NOT NULL REFERENCES properties(id),
  user_id uuid NOT NULL REFERENCES users(id),
  title text,
  is_primary_contact boolean DEFAULT false,
  UNIQUE(property_id, user_id)
);

CREATE TABLE cmc_assignments (
  id uuid PRIMARY KEY,
  property_id uuid NOT NULL REFERENCES properties(id),
  cmc_user_id uuid NOT NULL REFERENCES users(id),
  assigned_by_user_id uuid NOT NULL REFERENCES users(id),
  status assignment_status NOT NULL DEFAULT 'active',
  assigned_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  first_call_due_at timestamptz
);

CREATE TABLE training_statuses (
  id uuid PRIMARY KEY,
  property_id uuid NOT NULL REFERENCES properties(id),
  user_id uuid NOT NULL REFERENCES users(id),
  external_training_id text,
  status text NOT NULL,
  progress_percent int DEFAULT 0,
  required_modules int DEFAULT 0,
  completed_modules int DEFAULT 0,
  last_synced_at timestamptz,
  raw_payload jsonb,
  UNIQUE(property_id, user_id)
);

CREATE TABLE calls (
  id uuid PRIMARY KEY,
  property_id uuid NOT NULL REFERENCES properties(id),
  cmc_user_id uuid NOT NULL REFERENCES users(id),
  scheduled_by_user_id uuid NOT NULL REFERENCES users(id),
  call_type call_type NOT NULL,
  status call_status NOT NULL DEFAULT 'scheduled',
  start_time timestamptz NOT NULL,
  end_time timestamptz NOT NULL,
  timezone text NOT NULL,
  zoom_meeting_id text,
  zoom_join_url text,
  zoom_start_url text,
  outlook_event_id text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_calls_cmc_time ON calls(cmc_user_id, start_time, end_time);
CREATE INDEX idx_calls_property ON calls(property_id);
CREATE INDEX idx_training_property_user ON training_statuses(property_id, user_id);
