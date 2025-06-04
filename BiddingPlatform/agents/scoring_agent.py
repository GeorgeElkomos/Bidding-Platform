# agents/scoring_agent.py
from typing import Dict, Any, List, Tuple
import statistics
from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus

class ScoringAgent(BaseAgent):
    """Agent specialized in calculating scores and rankings for tender proposals"""
    
    def __init__(self, agent_id: str = None, config: Dict[str, Any] = None):
        super().__init__(agent_id, config)
        self.scoring_method = config.get('scoring_method', 'weighted_average') if config else 'weighted_average'
        self.normalization_enabled = config.get('normalization_enabled', True) if config else True
    
    def get_capabilities(self) -> List[str]:
        return [
            "weighted_scoring",
            "ranking_calculation", 
            "score_normalization",
            "tie_breaking",
            "statistical_analysis"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process scoring tasks"""
        task_type = task.input_data.get('task_type')
        
        if task_type == 'calculate_scores':
            return await self._calculate_total_scores(task)
        elif task_type == 'rank_companies':
            return await self._rank_companies(task)
        elif task_type == 'analyze_scores':
            return await self._analyze_score_distribution(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _calculate_total_scores(self, task: AgentTask) -> AgentResult:
        """Calculate total weighted scores for all companies"""
        analyses = task.input_data.get('analyses', [])
        criteria = task.input_data.get('criteria', [])
        
        if not analyses or not criteria:
            raise ValueError("Analyses and criteria required for scoring")
        
        # Create scoring matrix
        scoring_matrix = self._build_scoring_matrix(analyses, criteria)
        
        # Calculate weighted scores
        weighted_scores = self._calculate_weighted_scores(scoring_matrix, criteria)
        
        # Apply normalization if enabled
        if self.normalization_enabled:
            weighted_scores = self._normalize_scores(weighted_scores)
        
        # Calculate statistics
        score_statistics = self._calculate_score_statistics(weighted_scores)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'company_scores': weighted_scores,
                'scoring_matrix': scoring_matrix,
                'score_statistics': score_statistics,
                'normalization_applied': self.normalization_enabled
            }
        )
    
    async def _rank_companies(self, task: AgentTask) -> AgentResult:
        """Rank companies based on their total scores"""
        company_scores = task.input_data.get('company_scores', [])
        top_n = task.input_data.get('top_n', 3)
        
        if not company_scores:
            raise ValueError("Company scores required for ranking")
        
        # Sort companies by total score (descending)
        sorted_companies = sorted(
            company_scores, 
            key=lambda x: x['total_score'], 
            reverse=True
        )
        
        # Handle ties with additional criteria
        sorted_companies = self._handle_ties(sorted_companies)
        
        # Split into chosen and not chosen
        chosen = sorted_companies[:top_n]
        not_chosen = sorted_companies[top_n:]
        
        # Add rank information
        for i, company in enumerate(chosen):
            company['rank'] = i + 1
        
        # Calculate ranking statistics
        ranking_stats = self._calculate_ranking_statistics(sorted_companies, top_n)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'chosen': chosen,
                'not_chosen': not_chosen,
                'ranking_statistics': ranking_stats,
                'total_companies': len(sorted_companies)
            }
        )
    
    def _build_scoring_matrix(self, analyses: List[Dict], criteria: List[Dict]) -> Dict[str, Any]:
        """Build a comprehensive scoring matrix"""
        matrix = {
            'companies': [],
            'criteria': [c['name'] for c in criteria],
            'scores': {},
            'criterion_details': {}
        }
        
        for analysis in analyses:
            company_name = analysis.get('company_name')
            if not company_name:
                continue
                
            matrix['companies'].append(company_name)
            matrix['scores'][company_name] = {}
            matrix['criterion_details'][company_name] = {}
            
            # Extract scores for each criterion
            criterion_analyses = analysis.get('criterion_analyses', [])
            for criterion_analysis in criterion_analyses:
                criterion_name = criterion_analysis.get('criterion_name')
                score = criterion_analysis.get('score', 0)
                
                matrix['scores'][company_name][criterion_name] = score
                matrix['criterion_details'][company_name][criterion_name] = {
                    'score': score,
                    'strengths': criterion_analysis.get('strengths', []),
                    'weaknesses': criterion_analysis.get('weaknesses', []),
                    'evidence': criterion_analysis.get('evidence', []),
                    'justification': criterion_analysis.get('justification', '')
                }
        
        return matrix
    
    def _calculate_weighted_scores(self, matrix: Dict, criteria: List[Dict]) -> List[Dict[str, Any]]:
        """Calculate weighted total scores for each company"""
        company_scores = []
        
        # Create weight mapping
        weight_map = {c['name']: c.get('weight', 0) for c in criteria}
        total_weight = sum(weight_map.values())
        
        # Normalize weights to sum to 100
        if total_weight != 100 and total_weight > 0:
            for criterion_name in weight_map:
                weight_map[criterion_name] = (weight_map[criterion_name] / total_weight) * 100
        
        for company in matrix['companies']:
            company_data = {
                'company': company,
                'criterion_scores': {},
                'weighted_scores': {},
                'total_score': 0,
                'score_breakdown': []
            }
            
            total_weighted_score = 0
            
            for criterion in criteria:
                criterion_name = criterion['name']
                weight = weight_map.get(criterion_name, 0)
                raw_score = matrix['scores'][company].get(criterion_name, 0)
                weighted_score = (raw_score * weight) / 100
                
                company_data['criterion_scores'][criterion_name] = raw_score
                company_data['weighted_scores'][criterion_name] = weighted_score
                company_data['score_breakdown'].append({
                    'criterion': criterion_name,
                    'raw_score': raw_score,
                    'weight': weight,
                    'weighted_score': weighted_score
                })
                
                total_weighted_score += weighted_score
            
            company_data['total_score'] = round(total_weighted_score, 2)
            company_scores.append(company_data)
        
        return company_scores
    
    def _normalize_scores(self, company_scores: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize scores to improve distribution"""
        if len(company_scores) < 2:
            return company_scores
        
        # Extract total scores
        total_scores = [cs['total_score'] for cs in company_scores]
        
        # Calculate normalization parameters
        min_score = min(total_scores)
        max_score = max(total_scores)
        score_range = max_score - min_score
        
        # Only normalize if there's reasonable variation
        if score_range < 10:  # Not much variation, keep original scores
            return company_scores
        
        # Apply min-max normalization to 60-95 range (typical tender score range)
        normalized_min = 60
        normalized_max = 95
        normalized_range = normalized_max - normalized_min
        
        for company_data in company_scores:
            original_score = company_data['total_score']
            
            if score_range > 0:
                normalized_score = normalized_min + (
                    (original_score - min_score) / score_range * normalized_range
                )
            else:
                normalized_score = (normalized_min + normalized_max) / 2
            
            company_data['original_total_score'] = original_score
            company_data['total_score'] = round(normalized_score, 2)
        
        return company_scores
    
    def _handle_ties(self, sorted_companies: List[Dict]) -> List[Dict]:
        """Handle tied scores using secondary criteria"""
        if len(sorted_companies) <= 1:
            return sorted_companies
        
        # Group companies by score
        score_groups = {}
        for company in sorted_companies:
            score = company['total_score']
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(company)
        
        # Sort tied groups using secondary criteria
        final_ranking = []
        for score in sorted(score_groups.keys(), reverse=True):
            tied_companies = score_groups[score]
            
            if len(tied_companies) > 1:
                # Tie-breaking: use highest individual criterion score
                tied_companies.sort(
                    key=lambda x: max(x.get('criterion_scores', {}).values()),
                    reverse=True
                )
            
            final_ranking.extend(tied_companies)
        
        return final_ranking
    
    def _calculate_score_statistics(self, company_scores: List[Dict]) -> Dict[str, Any]:
        """Calculate statistical analysis of scores"""
        if not company_scores:
            return {}
        
        total_scores = [cs['total_score'] for cs in company_scores]
        
        stats = {
            'count': len(total_scores),
            'mean': round(statistics.mean(total_scores), 2),
            'median': round(statistics.median(total_scores), 2),
            'min': min(total_scores),
            'max': max(total_scores),
            'range': round(max(total_scores) - min(total_scores), 2),
            'std_dev': round(statistics.stdev(total_scores) if len(total_scores) > 1 else 0, 2)
        }
        
        # Add quartiles
        sorted_scores = sorted(total_scores)
        n = len(sorted_scores)
        if n >= 4:
            stats['q1'] = sorted_scores[n // 4]
            stats['q3'] = sorted_scores[3 * n // 4]
        
        # Calculate criterion-specific statistics
        criterion_stats = {}
        if company_scores:
            first_company = company_scores[0]
            for criterion_name in first_company.get('criterion_scores', {}):
                criterion_scores = [
                    cs.get('criterion_scores', {}).get(criterion_name, 0) 
                    for cs in company_scores
                ]
                
                criterion_stats[criterion_name] = {
                    'mean': round(statistics.mean(criterion_scores), 2),
                    'min': min(criterion_scores),
                    'max': max(criterion_scores),
                    'std_dev': round(statistics.stdev(criterion_scores) if len(criterion_scores) > 1 else 0, 2)
                }
        
        stats['criterion_statistics'] = criterion_stats
        return stats
    
    def _calculate_ranking_statistics(self, sorted_companies: List[Dict], top_n: int) -> Dict[str, Any]:
        """Calculate statistics about the ranking results"""
        if not sorted_companies:
            return {}
        
        chosen = sorted_companies[:top_n]
        not_chosen = sorted_companies[top_n:]
        
        chosen_scores = [c['total_score'] for c in chosen]
        not_chosen_scores = [c['total_score'] for c in not_chosen] if not_chosen else []
        
        stats = {
            'winner_threshold': min(chosen_scores) if chosen_scores else 0,
            'winner_spread': max(chosen_scores) - min(chosen_scores) if len(chosen_scores) > 1 else 0,
            'margin_to_next': (
                min(chosen_scores) - max(not_chosen_scores) 
                if chosen_scores and not_chosen_scores 
                else 0
            ),
            'competitive_ratio': len([c for c in sorted_companies if c['total_score'] >= 70]) / len(sorted_companies)
        }
        
        # Check for close competition
        if not_chosen_scores and chosen_scores:
            margin = min(chosen_scores) - max(not_chosen_scores)
            stats['close_competition'] = margin < 5.0
        else:
            stats['close_competition'] = False
        
        return stats
    
    async def _analyze_score_distribution(self, task: AgentTask) -> AgentResult:
        """Analyze the distribution of scores across criteria and companies"""
        company_scores = task.input_data.get('company_scores', [])
        
        if not company_scores:
            raise ValueError("Company scores required for distribution analysis")
        
        # Overall distribution analysis
        distribution_analysis = self._analyze_distribution_patterns(company_scores)
        
        # Criterion performance analysis
        criterion_analysis = self._analyze_criterion_performance(company_scores)
        
        # Outlier detection
        outliers = self._detect_outliers(company_scores)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'distribution_analysis': distribution_analysis,
                'criterion_analysis': criterion_analysis,
                'outliers': outliers,
                'total_companies_analyzed': len(company_scores)
            }
        )
    
    def _analyze_distribution_patterns(self, company_scores: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns in score distribution"""
        total_scores = [cs['total_score'] for cs in company_scores]
        
        # Score ranges
        ranges = {
            'excellent': len([s for s in total_scores if s >= 85]),
            'good': len([s for s in total_scores if 70 <= s < 85]),
            'average': len([s for s in total_scores if 50 <= s < 70]),
            'poor': len([s for s in total_scores if s < 50])
        }
        
        # Distribution shape
        mean_score = statistics.mean(total_scores)
        median_score = statistics.median(total_scores)
        
        skewness = "right" if mean_score > median_score else "left" if mean_score < median_score else "symmetric"
        
        return {
            'score_ranges': ranges,
            'distribution_shape': skewness,
            'concentration': max(ranges.values()) / len(total_scores),  # How concentrated scores are
            'quality_level': self._assess_overall_quality_level(ranges, len(total_scores))
        }
    
    def _analyze_criterion_performance(self, company_scores: List[Dict]) -> Dict[str, Any]:
        """Analyze performance across different criteria"""
        if not company_scores:
            return {}
        
        criterion_performance = {}
        first_company = company_scores[0]
        
        for criterion_name in first_company.get('criterion_scores', {}):
            criterion_scores = [
                cs.get('criterion_scores', {}).get(criterion_name, 0) 
                for cs in company_scores
            ]
            
            criterion_performance[criterion_name] = {
                'average_score': round(statistics.mean(criterion_scores), 2),
                'difficulty_level': self._assess_criterion_difficulty(criterion_scores),
                'discrimination_power': statistics.stdev(criterion_scores) if len(criterion_scores) > 1 else 0,
                'top_performers': len([s for s in criterion_scores if s >= 80])
            }
        
        return criterion_performance
    
    def _assess_criterion_difficulty(self, scores: List[float]) -> str:
        """Assess how difficult a criterion was based on average performance"""
        avg_score = statistics.mean(scores)
        
        if avg_score >= 80:
            return "سهل"
        elif avg_score >= 65:
            return "متوسط"
        elif avg_score >= 50:
            return "صعب"
        else:
            return "صعب جداً"
    
    def _assess_overall_quality_level(self, ranges: Dict[str, int], total: int) -> str:
        """Assess overall quality of submissions"""
        excellent_ratio = ranges['excellent'] / total
        good_ratio = ranges['good'] / total
        
        if excellent_ratio >= 0.3:
            return "جودة عالية"
        elif (excellent_ratio + good_ratio) >= 0.5:
            return "جودة جيدة"
        elif ranges['average'] / total >= 0.4:
            return "جودة متوسطة"
        else:
            return "جودة ضعيفة"
    
    def _detect_outliers(self, company_scores: List[Dict]) -> Dict[str, List[str]]:
        """Detect outlier companies with unusually high or low scores"""
        if len(company_scores) < 3:
            return {'high_outliers': [], 'low_outliers': []}
        
        total_scores = [cs['total_score'] for cs in company_scores]
        mean_score = statistics.mean(total_scores)
        std_dev = statistics.stdev(total_scores)
        
        threshold = 1.5 * std_dev  # 1.5 standard deviations
        
        high_outliers = []
        low_outliers = []
        
        for company_data in company_scores:
            score = company_data['total_score']
            company_name = company_data['company']
            
            if score > mean_score + threshold:
                high_outliers.append(company_name)
            elif score < mean_score - threshold:
                low_outliers.append(company_name)
        
        return {
            'high_outliers': high_outliers,
            'low_outliers': low_outliers
        }
