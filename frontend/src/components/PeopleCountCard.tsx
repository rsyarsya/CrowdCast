import styles from "./PeopleCountCard.module.css";

interface PeopleCountCardProps {
  people_count: number;
}

/**
 * PeopleCountCard renders the current people count prominently. Pure props-in;
 * no data fetching.
 */
export default function PeopleCountCard({ people_count }: PeopleCountCardProps) {
  return (
    <div className={styles.card}>
      <span className={styles.label}>Jumlah Orang</span>
      <span className={styles.count}>{people_count}</span>
    </div>
  );
}
