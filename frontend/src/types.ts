export type UserRole = "staff" | "owner" | "cmc" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_admin: boolean;
  zoom_user_id?: string | null;
}

export interface Property {
  id: string;
  name: string;
  address: string;
  old_tool_property_id?: string | null;
  new_tool_property_id?: string | null;
  transition_status: string;
  owner_user_id: string;
}

export interface TrainingStatus {
  id: string;
  property_id: string;
  user_id: string;
  status: string;
  progress_percent: number;
  required_modules: number;
  completed_modules: number;
  last_synced_at?: string | null;
}

export interface StaffTraining {
  user: User;
  training?: TrainingStatus | null;
  title?: string | null;
  is_primary_contact: boolean;
}

export interface Assignment {
  id: string;
  property: Property;
  cmc: User;
  assigned_at: string;
  first_call_due_at?: string | null;
  first_call_status: string;
}

export interface Slot {
  start_time: string;
  end_time: string;
  timezone: string;
}

export interface Call {
  id: string;
  property_id: string;
  cmc_user_id: string;
  scheduled_by_user_id: string;
  call_type: "first_call" | "follow_up";
  status: string;
  start_time: string;
  end_time: string;
  timezone: string;
  zoom_join_url?: string | null;
  outlook_event_id?: string | null;
}

export interface AdminDashboard {
  user: User;
  counts: {
    properties: number;
    staff_users: number;
    cmcs: number;
    open_first_calls: number;
    scheduled_calls: number;
  };
  properties: Property[];
  cmcs: User[];
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  sender: User;
  content: string;
  created_at: string;
  read_by: string[];
}

export interface ChatThread {
  id: string;
  property: Property;
  cmc_user: User;
  last_message: string | null;
  last_activity_at: string;
  unread_count: number;
}
