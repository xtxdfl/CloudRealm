// PolicyManagement.tsx
const PolicyManagement = () => {
  const [policies, setPolicies] =Policy[]>([]);

  const handleCreatePolicy = async (policy: PolicyCreateRequest) => {
    await axios.post('/api/v1/security/policies', policy);
    fetchPolicies();
  };

  return (
    <div>
      <PolicyForm onCreate={handleCreatePolicy} />
PolicyTable data={policies} />
    </div>
  );
};